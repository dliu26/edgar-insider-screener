from lxml import etree
import re
import logging
from ..models.schemas import FilingRecord

logger = logging.getLogger(__name__)

TECH_SIC_CODES = {"7370", "7371", "7372", "7374", "7379"}

# Matches the XML declaration or the ownershipDocument root, used to extract
# embedded XML from HTML-wrapped SEC filings.
_XML_START_RE = re.compile(rb"<\?xml\b|<ownershipDocument\b", re.IGNORECASE)


def _parse_root(xml_bytes: bytes, accession_number: str):
    """
    Return an lxml element tree for the Form 4 bytes, trying three strategies:

    1. Strict XML parser         — correct path for well-formed filings.
    2. Recovering XML parser     — heals minor malformations (stray &, etc.).
    3. XML extracted from HTML   — many EDGAR responses wrap the XML inside an
       HTML page (<html><head><meta …></head><body>…</body></html>).
       lxml's HTMLParser lowercases every tag name, so we CANNOT use it
       directly — instead we regex-extract the embedded XML and re-parse it.
    """
    # 1. Strict XML
    try:
        return etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError:
        pass

    # 2. Recovering XML
    try:
        root = etree.fromstring(xml_bytes, etree.XMLParser(recover=True))
        if root is not None and root.tag not in ("html", "HTML"):
            logger.debug(f"{accession_number}: used recovering XML parser")
            return root
    except Exception:
        pass

    # 3. The bytes look like HTML — extract the embedded XML and re-parse it.
    m = _XML_START_RE.search(xml_bytes)
    if m:
        inner = xml_bytes[m.start():]
        # Trim anything after the closing </ownershipDocument> tag
        end = inner.upper().rfind(b"</OWNERSHIPDOCUMENT>")
        if end != -1:
            inner = inner[: end + len(b"</ownershipDocument>")]
        try:
            root = etree.fromstring(inner)
            logger.debug(f"{accession_number}: extracted XML from HTML wrapper")
            return root
        except etree.XMLSyntaxError:
            pass
        try:
            root = etree.fromstring(inner, etree.XMLParser(recover=True))
            if root is not None:
                logger.debug(
                    f"{accession_number}: extracted + recovered XML from HTML wrapper"
                )
                return root
        except Exception:
            pass

    logger.warning(
        f"{accession_number}: all parse strategies failed — "
        f"first 120 bytes: {xml_bytes[:120]!r}"
    )
    return None


def parse_form4_xml(xml_bytes: bytes, accession_number: str, filing_url: str) -> list[FilingRecord]:
    """Parse a Form 4 XML and return FilingRecord list (one per P-type transaction)."""
    root = _parse_root(xml_bytes, accession_number)
    if root is None:
        return []

    # ── diagnostic: log root tag and top-level children ──────────────────
    logger.debug(
        f"{accession_number}: root tag = <{root.tag}>, "
        f"children = {[c.tag for c in root][:12]}"
    )

    def text(path: str) -> str:
        el = root.find(path)
        return el.text.strip() if el is not None and el.text else ""

    issuer_name = text(".//issuer/issuerName")
    issuer_cik  = text(".//issuer/issuerCik").zfill(10)
    ticker      = text(".//issuer/issuerTradingSymbol")

    reporting_owner = root.find(".//reportingOwner")
    if reporting_owner is None:
        logger.debug(f"{accession_number}: no <reportingOwner> found, skipping")
        return []

    insider_name = ""
    name_el = reporting_owner.find(".//rptOwnerName")
    if name_el is not None and name_el.text:
        insider_name = name_el.text.strip()

    insider_cik = ""
    cik_el = reporting_owner.find(".//rptOwnerCik")
    if cik_el is not None and cik_el.text:
        insider_cik = cik_el.text.strip().zfill(10)

    title = ""
    title_el = reporting_owner.find(".//officerTitle")
    if title_el is not None and title_el.text:
        title = title_el.text.strip()

    # Determine insider type and fill in missing title from relationship flags
    insider_type = "corporate"
    relationship = reporting_owner.find(".//reportingOwnerRelationship")
    if relationship is not None:
        def _flag(name: str) -> bool:
            el = relationship.find(name)
            return el is not None and el.text is not None and el.text.strip() == "1"

        is_ten_pct = _flag("isTenPercentOwner")
        is_director = _flag("isDirector")
        is_officer  = _flag("isOfficer")

        if is_ten_pct and not is_officer and not is_director:
            insider_type = "institutional"
        if not title:
            if is_director:
                title = "Director"
            elif is_ten_pct:
                title = "10% Owner"

    # ── find all non-derivative transactions and log codes ────────────────
    all_txns = root.findall(".//nonDerivativeTransaction")
    all_codes = []
    for t in all_txns:
        c = t.findtext(".//transactionCode", "").strip()
        all_codes.append(c)

    logger.debug(
        f"{accession_number}: issuer={issuer_name!r} ticker={ticker!r} "
        f"nonDerivativeTxns={len(all_txns)} codes={all_codes}"
    )

    records = []
    for txn in all_txns:
        # transactionCode lives inside <transactionCoding><transactionCode>
        code = txn.findtext(".//transactionCode", "").strip()
        if code != "P":
            continue

        plan_flag_el = txn.find(".//planFlag")
        is_10b51 = (
            plan_flag_el is not None
            and plan_flag_el.text is not None
            and plan_flag_el.text.strip() == "1"
        )

        txn_date       = txn.findtext(".//transactionDate/value", "").strip()
        shares_text    = txn.findtext(".//transactionShares/value", "0").strip()
        price_text     = txn.findtext(".//transactionPricePerShare/value", "0").strip()
        post_sh_text   = txn.findtext(".//sharesOwnedFollowingTransaction/value", "0").strip()

        try:
            shares     = float(shares_text)  if shares_text  else 0.0
            price      = float(price_text)   if price_text   else 0.0
            post_shares = float(post_sh_text) if post_sh_text else 0.0
        except ValueError:
            logger.debug(
                f"{accession_number}: skipping txn — bad numeric value "
                f"shares={shares_text!r} price={price_text!r}"
            )
            continue

        records.append(FilingRecord(
            id=accession_number,
            issuerName=issuer_name,
            ticker=ticker,
            issuerCik=issuer_cik,
            insiderName=insider_name,
            insiderCik=insider_cik,
            title=title,
            transactionDate=txn_date,
            transactionType="P",
            shares=shares,
            pricePerShare=price,
            totalValue=shares * price,
            postTransactionShares=post_shares,
            is10b51=is_10b51,
            marketCap=None,
            adtv=None,
            sector=None,
            insiderType=insider_type,
            signals=[],
            filingUrl=filing_url,
        ))

    if not records:
        logger.debug(
            f"{accession_number}: 0 P-type transactions "
            f"(all codes present: {all_codes})"
        )

    return records
