"""Assistant preview commits only importable rows; legacy endpoints stay strict."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_template_download_and_bank_partial_commit(settings, database):
    with TestClient(create_app(settings), headers={"X-SoloLMNP-Request": "1"}) as client:
        _seed(client)
        template = client.get("/api/operations/imports/bank/template")
        assert template.status_code == 200
        assert template.headers["content-type"].startswith("text/csv")
        assert "modele-releve-bancaire.csv" in template.headers["content-disposition"]
        text = template.content.decode("utf-8-sig")
        assert text.startswith("Date;Libellé;Montant;Référence")

        content = (
            "\ufeffDate;Libellé;Montant;Référence\n"
            "01/02/2025;Assurance PNO;-100,50;REL-1\n"
            "02/02/2025;Loyer Dupont;800,00;REL-2\n"
            "03/02/2025;Inconnu;abc;REL-3\n"
        )
        preview = client.post(
            "/api/operations/imports/bank/preview",
            json={"content": content, "bank_account_id": 1},
        )
        assert preview.status_code == 200, preview.text
        body = preview.json()
        assert body["summary"] == {
            "valid": 2,
            "duplicate": 0,
            "warning": 0,
            "error": 1,
            "count": 3,
            "importable": 2,
        }
        rejected = next(row for row in body["rows"] if row["status"] == "error")
        issue = next(item for item in rejected["issues"] if item["field"] == "amount")
        assert issue["line"] == 4
        assert issue["column"] == "Montant"
        assert issue["value"] == "abc"
        assert issue["correction"]
        assert issue["help"] == "import-csv"
        assert "abc" in body["rejects_csv"]
        assert body["rejects_csv"].startswith("\ufeff")

        committed = client.post(
            "/api/operations/imports/bank/commit",
            json={"content": content, "bank_account_id": 1, "mapping": body["mapping"]},
        )
        assert committed.status_code == 200, committed.text
        assert committed.json()["imported"] == 2
        stored = client.get("/api/operations/bank/transactions?bank_account_id=1").json()
        assert {row["external_reference"] for row in stored} == {"REL-1", "REL-2"}
        assert client.get("/api/ledger/entries?fiscal_year_id=1").json()["count"] == 0

        again = client.post(
            "/api/operations/imports/bank/preview",
            json={"content": content, "bank_account_id": 1},
        ).json()
        assert again["summary"]["duplicate"] == 2
        assert again["summary"]["importable"] == 0
        legacy = client.post(
            "/api/operations/bank/import",
            json={
                "bank_account_id": 1,
                "content": "date,label,amount,reference\n2025-02-01,Test,1,A\n",
            },
        )
        assert legacy.status_code == 422


def test_operations_commit_skips_conflicts_and_keeps_validated_entries(settings, database):
    with TestClient(create_app(settings), headers={"X-SoloLMNP-Request": "1"}) as client:
        _seed(client)
        first = (
            "Nature;Date;Type;Tiers;Montant;Libellé;Référence de pièce;Justificatif;Déjà payée\n"
            "Dépense;01/02/2025;ASS;Assureur;42,50;Assurance PNO;ASS-1;facture.pdf;oui\n"
        )
        assert (
            client.post(
                "/api/operations/imports/operations/commit",
                json={
                    "content": first,
                    "property_id": 1,
                    "fiscal_year_id": 1,
                    "bank_account_id": 1,
                },
            ).json()["imported"]
            == 1
        )
        original = client.get("/api/operations").json()[0]
        assert original["amount"] == "42.50"

        mixed = (
            "Nature;Date;Type;Tiers;Montant;Libellé;Référence de pièce\n"
            "Dépense;01/02/2025;ASS;Assureur;99,00;Assurance PNO;ASS-1\n"
            "Recette;02/02/2025;LOY;Dupont;800,00;Loyer février;LOY-1\n"
            "Dépense;01/01/2024;ASS;Assureur;10,00;Hors exercice;ASS-2024\n"
        )
        preview = client.post(
            "/api/operations/imports/operations/preview",
            json={
                "content": mixed,
                "property_id": 1,
                "fiscal_year_id": 1,
                "bank_account_id": 1,
            },
        )
        assert preview.status_code == 200, preview.text
        summary = preview.json()["summary"]
        assert summary["error"] == 2
        assert summary["importable"] == 1
        conflict = next(row for row in preview.json()["rows"] if row["line"] == 2)
        assert conflict["issues"][0]["column"] == "Référence de pièce"
        assert "42,50" not in conflict["issues"][0]["value"]
        outside = next(row for row in preview.json()["rows"] if row["line"] == 4)
        assert outside["issues"][0]["code"] == "DATE_OUTSIDE_YEAR"
        assert outside["issues"][0]["help"] == "exercice"
        committed = client.post(
            "/api/operations/imports/operations/commit",
            json={
                "content": mixed,
                "property_id": 1,
                "fiscal_year_id": 1,
                "bank_account_id": 1,
                "mapping": preview.json()["mapping"],
            },
        )
        assert committed.status_code == 200, committed.text
        assert committed.json()["imported"] == 1
        amounts = {
            row["description"]: row["amount"] for row in client.get("/api/operations").json()
        }
        assert amounts["Assurance PNO"] == "42.50"
        assert amounts["Loyer février"] == "800.00"
        assert "Hors exercice" not in amounts


def test_loan_preview_separates_warning_and_imports_only_arrived_rows(settings, database):
    with TestClient(create_app(settings), headers={"X-SoloLMNP-Request": "1"}) as client:
        _seed(client)
        created = client.post(
            "/api/operations/loans",
            json={
                "property_id": 1,
                "lender": "Banque fictive",
                "start_date": "2025-01-01",
                "initial_principal": "10000.00",
                "interest_rate": "3.50",
                "duration_months": 120,
                "principal_account": "164000",
            },
        )
        assert created.status_code == 201, created.text
        funded = client.post(
            "/api/operations/loans/1/fund",
            json={
                "request_id": "fund-loan-assistant",
                "fiscal_year_id": 1,
                "date": "2025-01-15",
                "piece_reference": "DEBLOC-1",
                "amount": "10000.00",
                "bank_account_id": 1,
            },
        )
        assert funded.status_code == 201, funded.text
        content = (
            "Prêt;Date;Date de débit;Capital;Intérêts;Assurance banque;Total banque\n"
            "PRET-1;05/03/2025;05/03/2025;100,00;20,00;5,00;125,00\n"
            "PRET-1;05/01/2026;05/01/2026;100,00;20,00;5,00;125,00\n"
            "PRET-1;05/04/2025;05/04/2025;100,00;20,00;5,00;50,00\n"
        )
        preview = client.post(
            "/api/operations/imports/loan_payments/preview",
            json={
                "content": content,
                "loan_id": 1,
                "fiscal_year_id": 1,
                "bank_account_id": 1,
            },
        )
        assert preview.status_code == 200, preview.text
        body = preview.json()
        assert body["loan_reference"] == "PRET-1"
        assert body["summary"]["valid"] == 1
        assert body["summary"]["warning"] == 1
        assert body["summary"]["error"] == 1
        assert body["summary"]["importable"] == 1
        warning = next(row for row in body["rows"] if row["status"] == "warning")
        assert warning["importable"] is False
        assert warning["warnings"][0]["column"] == "Date de débit"
        refused = client.post(
            "/api/operations/imports/loan_payments/commit",
            json={
                "content": content,
                "loan_id": 1,
                "fiscal_year_id": 1,
                "bank_account_id": 1,
            },
        )
        assert refused.status_code == 409
        assert refused.json()["detail"]["code"] == "LOAN_PREVIEW_REQUIRED"
        assert refused.json()["detail"]["help"] == "emprunt"
        committed = client.post(
            "/api/operations/imports/loan_payments/commit",
            json={
                "content": content,
                "loan_id": 1,
                "fiscal_year_id": 1,
                "bank_account_id": 1,
                "confirmed_loan_reference": "PRET-1",
                "mapping": body["mapping"],
            },
        )
        assert committed.status_code == 200, committed.text
        assert committed.json()["imported"] == 1
        payments = [
            row for row in client.get("/api/operations").json() if row["kind"] == "LOAN_PAYMENT"
        ]
        assert len(payments) == 1
        assert payments[0]["amount"] == "125.00"
        assert payments[0]["principal"] == "100.00"


def _seed(client: TestClient) -> None:
    assert (
        client.post(
            "/api/ledger/activity",
            json={"activity_name": "Assistant fictif", "activity_start_date": "2025-01-01"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/ledger/years",
            json={
                "year": 2025,
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "fiscal_vintage": "2025",
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/operations/properties",
            json={
                "name": "Bien fictif",
                "address": "Adresse fictive",
                "acquisition_date": "2025-01-01",
                "acquisition_price": "100000.00",
                "land_value": "20000.00",
                "building_value": "80000.00",
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/operations/banks",
            json={"name": "Banque fictive", "account_number": "512000"},
        ).status_code
        == 201
    )
