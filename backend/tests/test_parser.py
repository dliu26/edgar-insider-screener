import pytest
from app.services.filing_parser import parse_form4_xml

SAMPLE_FORM4_XML = b"""<?xml version="1.0"?>
<ownershipDocument>
  <issuer>
    <issuerCik>0001234567</issuerCik>
    <issuerName>Acme Tech Corp</issuerName>
    <issuerTradingSymbol>ACME</issuerTradingSymbol>
  </issuer>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerCik>0009876543</rptOwnerCik>
      <rptOwnerName>Jane Doe</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>0</isDirector>
      <isOfficer>1</isOfficer>
      <officerTitle>CEO</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2024-01-15</value></transactionDate>
      <transactionCoding>
        <transactionCode>P</transactionCode>
        <planFlag>0</planFlag>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>50000</value></transactionShares>
        <transactionPricePerShare><value>12.50</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts>
        <sharesOwnedFollowingTransaction><value>250000</value></sharesOwnedFollowingTransaction>
      </postTransactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
"""


def test_parse_purchase():
    records = parse_form4_xml(SAMPLE_FORM4_XML, "0001234567-24-000001", "https://www.sec.gov/test")
    assert len(records) == 1
    r = records[0]
    assert r.ticker == "ACME"
    assert r.insiderName == "Jane Doe"
    assert r.title == "CEO"
    assert r.shares == 50000.0
    assert r.pricePerShare == 12.50
    assert r.totalValue == 625000.0
    assert r.is10b51 is False
    assert r.transactionType == "P"


def test_skip_non_purchase():
    xml = SAMPLE_FORM4_XML.replace(b"<transactionCode>P</transactionCode>", b"<transactionCode>S</transactionCode>")
    records = parse_form4_xml(xml, "0001234567-24-000002", "https://www.sec.gov/test")
    assert len(records) == 0


def test_skip_10b51():
    xml = SAMPLE_FORM4_XML.replace(b"<planFlag>0</planFlag>", b"<planFlag>1</planFlag>")
    records = parse_form4_xml(xml, "0001234567-24-000003", "https://www.sec.gov/test")
    # Parser returns record, pipeline filters 10b51 - parser includes it
    assert len(records) == 1
    assert records[0].is10b51 is True


def test_signal_high_conviction():
    from app.services.signal_detector import detect_high_conviction
    from app.models.schemas import FilingRecord

    filing = FilingRecord(
        id="test",
        issuerName="Test Co",
        ticker="TEST",
        issuerCik="0000000001",
        insiderName="John CEO",
        insiderCik="0000000002",
        title="CEO",
        transactionDate="2024-01-15",
        transactionType="P",
        shares=100000,
        pricePerShare=60,
        totalValue=6_000_000,  # 12x CEO comp of $500k
        postTransactionShares=200000,
        is10b51=False,
        marketCap=500_000_000,
        signals=[],
        filingUrl="https://example.com",
    )
    assert detect_high_conviction(filing) is True


def test_signal_cluster_buy():
    from app.services.signal_detector import detect_cluster_buy
    from app.models.schemas import FilingRecord

    def make_filing(insider_cik, issuer_cik="0000000001"):
        return FilingRecord(
            id=f"test-{insider_cik}",
            issuerName="Test Co",
            ticker="TEST",
            issuerCik=issuer_cik,
            insiderName="Insider",
            insiderCik=insider_cik,
            title="Director",
            transactionDate="2024-01-15",
            transactionType="P",
            shares=1000,
            pricePerShare=10,
            totalValue=10000,
            postTransactionShares=5000,
            is10b51=False,
            marketCap=None,
            signals=[],
            filingUrl="https://example.com",
        )

    filings = [make_filing("0000000002"), make_filing("0000000003")]
    cluster = detect_cluster_buy(filings)
    assert "0000000001" in cluster

    single = [make_filing("0000000002")]
    assert detect_cluster_buy(single) == set()
