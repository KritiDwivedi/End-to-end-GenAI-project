from app.retrieval.query_processing import process_query


def test_extracts_terms_from_revenue_question() -> None:
    processed = process_query("What was Apple's total revenue in fiscal year 2021?")

    assert processed.keyword_terms == ["apple", "revenue", "2021"]
    assert processed.sparse_query == "apple OR revenue OR 2021"


def test_extracts_company_risk_terms() -> None:
    processed = process_query("Which cybersecurity risks does Microsoft identify?")

    assert processed.keyword_terms == ["cybersecurity", "risks", "microsoft"]


def test_caps_terms_at_five() -> None:
    processed = process_query(
        "Compare Apple's revenue, operating income, expenses, assets, debt, and cash in 2023."
    )

    assert len(processed.keyword_terms) == 5
    assert "2023" in processed.keyword_terms


def test_falls_back_for_query_without_meaningful_terms() -> None:
    processed = process_query("What is it?")

    assert processed.keyword_terms == []
    assert processed.sparse_query == "What is it?"
