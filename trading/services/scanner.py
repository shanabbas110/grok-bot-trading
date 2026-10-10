import logging
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

import requests
from django.conf import settings

from trading.models import ScannedToken, TokenStatus
from trading.services.activity import log_activity

logger = logging.getLogger(__name__)

DEX_BASE = "https://api.dexscreener.com"
GECKO_BASE = "https://api.geckoterminal.com/api/v2"


class MarketScanner:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json", "User-Agent": "GrokBot/1.0"})

    def scan(self) -> list[ScannedToken]:
        candidates: list[dict] = []
        candidates.extend(self._dex_token_boosts())
        candidates.extend(self._dex_token_profiles())
        candidates.extend(self._gecko_trending())
        candidates.extend(self._dex_search_solana())

        seen = set()
        saved: list[ScannedToken] = []
        for c in candidates:
            key = (c.get("symbol", "").upper(), c.get("chain", ""), c.get("token_address", ""))
            if not key[0] or key in seen:
                continue
            seen.add(key)
            if not self._passes_filters(c):
                self._upsert_token_status(c, rejected=True, detail=c.get("reject_reason", "FILTER"))
                continue
            rug = self._rug_check(c)
            c["rug_notes"] = rug.get("notes", {})
            c["rug_score"] = rug.get("score")
            if rug.get("reject"):
                self._upsert_token_status(c, rejected=True, detail=rug.get("detail", "RUG"))
                log_activity("risk", f"{c['symbol']}: {rug.get('detail', 'rug check failed')}", symbol=c["symbol"])
                continue

            token = self._save_token(c)
            saved.append(token)
            self._upsert_token_status(c, rejected=False, detail="APPROVED")

        log_activity(
            "scan",
            f"Scan complete: {len(candidates)} raw, {len(saved)} passed filters",
        )
        return saved

    def _passes_filters(self, c: dict) -> bool:
        liq = float(c.get("liquidity_usd") or 0)
        vol = float(c.get("volume_24h") or 0)
        ratio = float(c.get("buy_sell_ratio") or 0)
        age = c.get("pair_age_hours")
        fdv = c.get("fdv_usd")
        if liq < settings.SCAN_MIN_LIQUIDITY_USD:
            c["reject_reason"] = "LOW LP"
            return False
        if vol < settings.SCAN_MIN_VOLUME_24H:
            c["reject_reason"] = "LOW VOL"
            return False
        if ratio < settings.SCAN_MIN_BUY_SELL_RATIO:
            c["reject_reason"] = "BUY/SELL"
            return False
        if age is not None and float(age) > settings.SCAN_MAX_PAIR_AGE_HOURS:
            c["reject_reason"] = "AGE"
            return False
        if fdv and liq > 0:
            if float(fdv) / liq > settings.SCAN_MAX_FDV_LIQUIDITY_RATIO:
                c["reject_reason"] = "FDV/LP"
                return False
        return True

    def _rug_check(self, c: dict) -> dict:
        chain = (c.get("chain") or "").lower()
        addr = c.get("token_address") or ""
        notes = {}
        score = 80.0
        reject = False
        detail = ""

        if chain == "solana" and addr:
            try:
                r = self.session.get(f"https://api.rugcheck.xyz/v1/tokens/{addr}/report/summary", timeout=8)
                if r.ok:
                    data = r.json()
                    risk = data.get("riskLevel") or data.get("score")
                    notes["rugcheck"] = data
                    if isinstance(risk, str) and risk.lower() in ("high", "danger"):
                        reject = True
                        detail = "RUGCHECK HIGH"
                    if isinstance(risk, (int, float)) and risk > 70:
                        reject = True
                        detail = "RUGCHECK SCORE"
            except requests.RequestException as e:
                logger.debug("rugcheck error: %s", e)

        if addr and chain in ("ethereum", "bsc", "base", "solana"):
            chain_id = {"ethereum": "1", "bsc": "56", "base": "8453", "solana": "solana"}.get(chain, "1")
            try:
                r = self.session.get(
                    f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}",
                    params={"contract_addresses": addr},
                    timeout=8,
                )
                if r.ok:
                    result = r.json().get("result") or {}
                    payload = result.get(addr.lower(), {}) or result.get(addr, {})
                    notes["goplus"] = payload
                    if payload:
                        if payload.get("is_honeypot") == "1":
                            reject = True
                            detail = "HONEYPOT"
                        dev_pct = payload.get("owner_percent") or payload.get("creator_percent")
                        if dev_pct and float(dev_pct) > 0.15:
                            score -= 20
                            detail = detail or "DEV % HIGH"
                            log_activity("warn", f"Skipping {c.get('symbol')}: dev wallet {float(dev_pct)*100:.1f}%", symbol=c.get("symbol", ""))
            except requests.RequestException as e:
                logger.debug("goplus error: %s", e)

        if notes.get("rugcheck"):
            lp = notes["rugcheck"].get("markets", [{}])
            if lp:
                notes["lp_locked"] = True
                log_activity("risk", f"{c.get('symbol')}: LP check OK", symbol=c.get("symbol", ""))

        return {"reject": reject, "detail": detail, "notes": notes, "score": score}

    def _save_token(self, c: dict) -> ScannedToken:
        obj, _ = ScannedToken.objects.update_or_create(
            symbol=c["symbol"].upper(),
            chain=c.get("chain", ""),
            token_address=c.get("token_address", ""),
            defaults={
                "name": c.get("name", ""),
                "pair_address": c.get("pair_address", ""),
                "price_usd": Decimal(str(c.get("price_usd") or 0)),
                "liquidity_usd": Decimal(str(c.get("liquidity_usd") or 0)),
                "volume_24h": Decimal(str(c.get("volume_24h") or 0)),
                "buy_sell_ratio": Decimal(str(c.get("buy_sell_ratio") or 1)),
                "pair_age_hours": Decimal(str(c.get("pair_age_hours"))) if c.get("pair_age_hours") else None,
                "fdv_usd": Decimal(str(c.get("fdv_usd"))) if c.get("fdv_usd") else None,
                "rug_score": Decimal(str(c.get("rug_score"))) if c.get("rug_score") else None,
                "rug_notes": c.get("rug_notes") or {},
                "source": c.get("source", "dexscreener"),
            },
        )
        return obj

    def _upsert_token_status(self, c: dict, rejected: bool, detail: str):
        TokenStatus.objects.create(
            symbol=c.get("symbol", "").upper(),
            chain=c.get("chain", ""),
            state=TokenStatus.State.REJECTED if rejected else TokenStatus.State.APPROVED,
            detail=detail,
            is_positive=not rejected,
        )

    def _pair_to_candidate(self, pair: dict, source: str) -> dict | None:
        base = pair.get("baseToken") or {}
        symbol = base.get("symbol") or ""
        if not symbol:
            return None
        liq = (pair.get("liquidity") or {}).get("usd") or 0
        vol = (pair.get("volume") or {}).get("h24") or 0
        txns = pair.get("txns") or {}
        buys = (txns.get("h24") or {}).get("buys") or 0
        sells = (txns.get("h24") or {}).get("sells") or 0
        ratio = (buys / sells) if sells else (buys or 1)
        created = pair.get("pairCreatedAt")
        age_hours = None
        if created:
            try:
                ts = created / 1000 if created > 10_000_000_000 else created
                dt = datetime.fromtimestamp(ts, tz=dt_timezone.utc)
                age_hours = (datetime.now(dt_timezone.utc) - dt).total_seconds() / 3600
            except (TypeError, ValueError, OSError):
                pass
        return {
            "symbol": symbol,
            "name": base.get("name", ""),
            "chain": pair.get("chainId", ""),
            "token_address": base.get("address", ""),
            "pair_address": pair.get("pairAddress", ""),
            "price_usd": pair.get("priceUsd") or 0,
            "liquidity_usd": liq,
            "volume_24h": vol,
            "buy_sell_ratio": ratio,
            "pair_age_hours": age_hours,
            "fdv_usd": pair.get("fdv"),
            "source": source,
        }

    def _dex_token_boosts(self) -> list[dict]:
        out = []
        try:
            r = self.session.get(f"{DEX_BASE}/token-boosts/latest/v1", timeout=10)
            if r.ok:
                for item in r.json() if isinstance(r.json(), list) else []:
                    chain = item.get("chainId", "")
                    addr = item.get("tokenAddress", "")
                    if not addr:
                        continue
                    pairs = self._fetch_dex_pair(chain, addr)
                    out.extend(pairs)
        except requests.RequestException as e:
            logger.warning("dex boosts: %s", e)
        return out

    def _dex_token_profiles(self) -> list[dict]:
        out = []
        try:
            r = self.session.get(f"{DEX_BASE}/token-profiles/latest/v1", timeout=10)
            if r.ok:
                for item in r.json() if isinstance(r.json(), list) else []:
                    chain = item.get("chainId", "")
                    addr = item.get("tokenAddress", "")
                    if addr:
                        out.extend(self._fetch_dex_pair(chain, addr))
        except requests.RequestException as e:
            logger.warning("dex profiles: %s", e)
        return out

    def _fetch_dex_pair(self, chain: str, token_address: str) -> list[dict]:
        out = []
        try:
            r = self.session.get(f"{DEX_BASE}/latest/dex/tokens/{token_address}", timeout=10)
            if r.ok:
                pairs = r.json().get("pairs") or []
                for p in pairs[:3]:
                    if chain and p.get("chainId") != chain:
                        continue
                    c = self._pair_to_candidate(p, "dexscreener")
                    if c:
                        out.append(c)
        except requests.RequestException:
            pass
        return out

    def _dex_search_solana(self) -> list[dict]:
        out = []
        try:
            r = self.session.get(f"{DEX_BASE}/latest/dex/search", params={"q": "SOL"}, timeout=10)
            if r.ok:
                for p in (r.json().get("pairs") or [])[:15]:
                    c = self._pair_to_candidate(p, "dexscreener")
                    if c:
                        out.append(c)
        except requests.RequestException as e:
            logger.warning("dex search: %s", e)
        return out

    def _gecko_trending(self) -> list[dict]:
        out = []
        try:
            r = self.session.get(f"{GECKO_BASE}/networks/solana/trending_pools", timeout=10)
            if not r.ok:
                return out
            for item in (r.json().get("data") or [])[:20]:
                attrs = item.get("attributes") or {}
                name = attrs.get("name", "")
                symbol = name.split("/")[0].strip() if "/" in name else name[:12]
                liq = float(attrs.get("reserve_in_usd") or 0)
                vol = float((attrs.get("volume_usd") or {}).get("h24") or 0)
                price = float(attrs.get("base_token_price_usd") or 0)
                rel = (item.get("relationships") or {}).get("base_token", {}).get("data", {})
                token_id = rel.get("id", "")
                token_address = token_id.split("_")[-1] if "_" in token_id else ""
                out.append(
                    {
                        "symbol": symbol or "UNK",
                        "name": name,
                        "chain": "solana",
                        "token_address": token_address,
                        "pair_address": attrs.get("address", ""),
                        "price_usd": price,
                        "liquidity_usd": liq,
                        "volume_24h": vol,
                        "buy_sell_ratio": 1.2,
                        "pair_age_hours": None,
                        "fdv_usd": attrs.get("fdv_usd"),
                        "source": "geckoterminal",
                    }
                )
        except requests.RequestException as e:
            logger.warning("gecko trending: %s", e)
        return out
