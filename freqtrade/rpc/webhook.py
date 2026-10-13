"""
This module manages webhook communication
"""

import logging
import threading
import time
from typing import Any

from requests import RequestException, post

from freqtrade.constants import Config
from freqtrade.enums import RPCMessageType
from freqtrade.rpc import RPC, RPCHandler
from freqtrade.rpc.rpc_types import RPCSendMsg


logger = logging.getLogger(__name__)

logger.debug("Included module rpc.webhook ...")


class Webhook(RPCHandler):
    """This class handles all webhook communication"""

    def __init__(self, rpc: RPC, config: Config) -> None:
        """
        Init the Webhook class, and init the super class RPCHandler
        :param rpc: instance of RPC Helper class
        :param config: Configuration object
        :return: None
        """
        super().__init__(rpc, config)

        self._url = self._config["webhook"]["url"]
        self._format = self._config["webhook"].get("format", "form")
        self._retries = self._config["webhook"].get("retries", 0)
        self._retry_delay = self._config["webhook"].get("retry_delay", 0.1)
        self._timeout = self._config["webhook"].get("timeout", 10)

        # 启动通知: freqtrade 在启动阶段会连发多条 startup(概览 / Searching pairs / Protections),
        # 这里开一个短合并窗口, 把窗口内的多条合并成一张卡片, 保证启动后第一时间收到且只有 1 条。
        self._startup_buf: list[str] = []
        self._startup_timer: threading.Timer | None = None
        self._startup_merge_delay = self._config["webhook"].get("startup_merge_delay", 1.5)

    def cleanup(self) -> None:
        """
        Cleanup pending module resources.
        This will do nothing for webhooks, they will simply not be called anymore
        """

    def _get_value_dict(self, msg: RPCSendMsg) -> dict[str, Any] | None:
        whconfig = self._config["webhook"]
        if msg["type"].value in whconfig:
            # Explicit types should have priority
            valuedict = whconfig.get(msg["type"].value)
        # The below is deprecated 2022.10 - only keep generic method.
        elif msg["type"] in [RPCMessageType.ENTRY]:
            valuedict = whconfig.get("webhookentry")
        elif msg["type"] in [RPCMessageType.ENTRY_CANCEL]:
            valuedict = whconfig.get("webhookentrycancel")
        elif msg["type"] in [RPCMessageType.ENTRY_FILL]:
            valuedict = whconfig.get("webhookentryfill")
        elif msg["type"] == RPCMessageType.EXIT:
            valuedict = whconfig.get("webhookexit")
        elif msg["type"] == RPCMessageType.EXIT_FILL:
            valuedict = whconfig.get("webhookexitfill")
        elif msg["type"] == RPCMessageType.EXIT_CANCEL:
            valuedict = whconfig.get("webhookexitcancel")
        elif msg["type"] in (
            RPCMessageType.STATUS,
            RPCMessageType.STARTUP,
            RPCMessageType.EXCEPTION,
            RPCMessageType.WARNING,
        ):
            valuedict = whconfig.get("webhookstatus")
        elif msg["type"] in (
            RPCMessageType.PROTECTION_TRIGGER,
            RPCMessageType.PROTECTION_TRIGGER_GLOBAL,
            RPCMessageType.LIQUIDATION_WARNING,
            RPCMessageType.WHITELIST,
            RPCMessageType.ANALYZED_DF,
            RPCMessageType.NEW_CANDLE,
            RPCMessageType.STRATEGY_MSG,
        ):
            # Don't fail for non-implemented types
            return None
        return valuedict

    def recursive_format(self, obj: dict | list | str, msg: RPCSendMsg):
        """
        Format the given object using the provided message.
        """
        match obj:
            case dict():
                return {k: self.recursive_format(v, msg) for k, v in obj.items()}
            case list():
                return [self.recursive_format(item, msg) for item in obj]
            case str():
                return obj.format(**msg)
            case _:
                return obj

    def _queue_startup(self, msg: RPCSendMsg) -> None:
        """缓存启动消息, 到点合并成一条发出 (不阻塞主流程)"""
        self._startup_buf.append(str(msg.get("status") or ""))
        if self._startup_timer is None:
            self._startup_timer = threading.Timer(self._startup_merge_delay, self._flush_startup)
            self._startup_timer.daemon = True
            self._startup_timer.start()

    def _flush_startup(self) -> None:
        try:
            raw = "\n\n---\n\n".join(s for s in self._startup_buf if s)
            self._startup_buf = []
            self._startup_timer = None
            status = self._shrink_startup(raw)
            if status:
                self._send_startup(status)
        except Exception:
            logger.exception("启动通知合并发送失败")

    @staticmethod
    def _shrink_startup(raw: str) -> str:
        """启动文案只保留关键行, 顺带把 telegram 风格(*粗体*/`代码`)转成飞书 lark_md 的 **粗体**。
        丢弃项: Minimum ROI(一长串字典) / Searching for ...(整段 pairlist filter 描述)。
        """
        keep = (
            "**Exchange:**",
            "**Stake per trade:**",
            "**Stoploss:**",
            "**Position adjustment:**",
            "**Timeframe:**",
            "**Strategy:**",
        )
        clean = raw.replace("*", "**").replace("`", "")
        # 命中不到关键行说明这是纯 Searching for / Protections 之类的冗长段, 返回空 -> 不发卡片
        return "\n".join(ln.strip() for ln in clean.splitlines() if ln.strip().startswith(keep))

    def _send_startup(self, status: str) -> None:
        valuedict = self._config["webhook"].get("startup")
        if not valuedict:
            logger.debug("webhook 未配置 startup 模板, 跳过启动通知")
            return
        msg = {"type": RPCMessageType.STARTUP, "status": status,
               "strategy": self._config.get("strategy", "")}
        try:
            self._send_msg(self.recursive_format(valuedict, msg), "startup")
        except KeyError as exc:
            logger.exception(
                "Problem calling Webhook(startup). Please check your webhook configuration. "
                "Exception: %s", exc,
            )

    def send_msg(self, msg: RPCSendMsg) -> None:
        """Send a message to telegram channel"""
        try:
            # 启动消息走合并窗口, 避免连发多条
            if msg["type"] == RPCMessageType.STARTUP:
                self._queue_startup(msg)
                return

            # 自定义注入: 飞书卡片需要策略名, 但 RPC 消息里没有该字段, 这里从 config 补齐
            # (缺失会触发 recursive_format 的 KeyError, 导致整条通知静默丢失)
            if isinstance(msg, dict) and "strategy" not in msg:
                msg["strategy"] = self._config.get("strategy", "")

            valuedict = self._get_value_dict(msg)

            if not valuedict:
                logger.debug("Message type '%s' not configured for webhooks", msg["type"])
                return

            payload = self.recursive_format(valuedict, msg)
            self._send_msg(payload, msg["type"].value)
        except KeyError as exc:
            logger.exception(
                "Problem calling Webhook. Please check your webhook configuration. Exception: %s",
                exc,
            )

    def _send_msg(self, payload: dict, msg_type: str = "") -> None:
        """do the actual call to the webhook"""

        success = False
        attempts = 0
        while not success and attempts <= self._retries:
            if attempts:
                if self._retry_delay:
                    time.sleep(self._retry_delay)
                logger.info("Retrying webhook...")

            attempts += 1

            try:
                if self._format == "form":
                    response = post(self._url, data=payload, timeout=self._timeout)
                elif self._format == "json":
                    response = post(self._url, json=payload, timeout=self._timeout)
                elif self._format == "raw":
                    response = post(
                        self._url,
                        data=payload["data"],
                        headers={"Content-Type": "text/plain"},
                        timeout=self._timeout,
                    )
                else:
                    raise NotImplementedError(f"Unknown format: {self._format}")

                # Throw a RequestException if the post was not successful
                response.raise_for_status()
                success = True
                logger.info(
                    "Webhook 已发送 [%s] -> HTTP %s | body=%s",
                    msg_type, response.status_code, response.text[:300],
                )

            except RequestException as exc:
                logger.warning("Could not call webhook url. Exception: %s", exc)
