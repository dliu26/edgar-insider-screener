from lxml import etree
from datetime import date
import logging
from ..models.schemas import FilingRecord

logger = logging.getLogger(__name__)

TECH_SIC_CODES = {"7370", "7371", "7372", "7374", "7379"}


def parse_form4_xml(xml_bytes: bytes, accession_number: str, filing_url: str) -> list[FilingRecord]:
    """Parse a Form 4 XML and return FilingRecord list (one per P-type transaction)."""
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as e:
        logger.error(f"XML parse error for {accession_number}: {e}")
        return []

    def text(path: str) -> str:
        el = root.find(path)
        return el.text.strip() if el is not None and el.text else ""

    issuer_name = text(".//issuer/issuerName")
    issuer_cik = text(".//issuer/issuerCik").zfill(10)
    ticker = text(".//issuer/issuerTradingSymbol")

    reporting_owner = root.find(".//reportingOwner")
    if reporting_owner is None:
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

    relationship = reporting_owner.find(".//reportingOwnerRelationship")
    if relationship is not None and not title:
        is_director = relationship.find("isDirector")
        if is_director is not None and is_director.text == "1":
            title = "Director"

    records = []
    for txn in root.findall(".//nonDerivativeTransaction"):
        code_el = txn.find(".//transactionCode")
        if code_el is None or code_el.text != "P":
            continue

        plan_flag_el = txn.find(".//planFlag")
        is_10b51 = False
        if plan_flag_el is not None and plan_flag_el.text:
            is_10b51 = plan_flag_el.text.strip() == "1"

        txn_date = txn.findtext(".//transactionDate/value", "").strip()
        shares_text = txn.findtext(".//transactionShares/value", "0").strip()
        price_text = txn.findtext(".//transactionPricePerShare/value", "0").strip()
        post_shares_text = txn.findtext(".//sharesOwnedFollowingTransaction/value", "0").strip()

        try:
            shares = float(shares_text) if shares_text else 0.0
            price = float(price_text) if price_text else 0.0
            post_shares = float(post_shares_text) if post_shares_text else 0.0
        except ValueError:
            continue

        total_value = shares * price

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
            totalValue=total_value,
            postTransactionShares=post_shares,
            is10b51=is_10b51,
            marketCap=None,
            signals=[],
            filingUrl=filing_url,
        ))

    return records
