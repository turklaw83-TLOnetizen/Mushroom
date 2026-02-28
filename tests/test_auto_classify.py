# Tests for core/ingest.auto_classify_file — zero-cost document classification

import pytest
from core.ingest import auto_classify_file


class TestFilenamePatterns:
    def test_police_report(self):
        assert auto_classify_file("Police_Report_2025.pdf") == "Police Report"

    def test_incident_report(self):
        assert auto_classify_file("Incident Report - Case 123.pdf") == "Police Report"

    def test_witness_statement(self):
        assert auto_classify_file("witness_statement_jones.pdf") == "Witness Statement"

    def test_medical_records(self):
        assert auto_classify_file("medical_records_doe.pdf") == "Medical Records"

    def test_financial_records(self):
        assert auto_classify_file("bank_statement_2024.pdf") == "Financial Records"

    def test_court_filing(self):
        assert auto_classify_file("Motion to Dismiss.pdf") == "Court Filing"

    def test_expert_report(self):
        assert auto_classify_file("Forensic_Lab_Report.pdf") == "Expert Report"

    def test_correspondence(self):
        assert auto_classify_file("email_from_client.pdf") == "Correspondence"

    def test_contract(self):
        assert auto_classify_file("lease_agreement_2023.pdf") == "Contract/Agreement"

    def test_deposition(self):
        assert auto_classify_file("Deposition_of_Smith.pdf") == "Deposition"

    def test_discovery(self):
        assert auto_classify_file("Discovery_Request_Set1.pdf") == "Discovery"

    def test_unrecognized_returns_none(self):
        assert auto_classify_file("document_123.pdf") is None


class TestExtensionPatterns:
    def test_jpg_is_photo(self):
        assert auto_classify_file("IMG_20250101.jpg") == "Photos/Video"

    def test_png_is_photo(self):
        assert auto_classify_file("screenshot.png") == "Photos/Video"

    def test_mp4_is_video(self):
        assert auto_classify_file("bodycam_footage.mp4") == "Photos/Video"


class TestContentPatterns:
    def test_police_department_header(self):
        header = "METROPOLITAN POLICE DEPARTMENT\nINCIDENT REPORT\nCase No: 2025-12345"
        assert auto_classify_file("unknown.pdf", header) == "Police Report"

    def test_medical_record_header(self):
        header = "PATIENT NAME: John Doe\nMEDICAL RECORD #: 12345\nDISCHARGE SUMMARY"
        assert auto_classify_file("doc.pdf", header) == "Medical Records"

    def test_court_header(self):
        header = "IN THE SUPERIOR COURT OF THE STATE OF GEORGIA\nCASE NO. 2025-CV-1234"
        assert auto_classify_file("filing.pdf", header) == "Court Filing"

    def test_deposition_header(self):
        header = "DEPOSITION OF JANE SMITH\nTaken on March 15, 2025"
        assert auto_classify_file("transcript.pdf", header) == "Deposition"


class TestPriority:
    def test_filename_takes_priority_over_content(self):
        # Filename says police, content says medical
        header = "PATIENT NAME: John Doe"
        assert auto_classify_file("police_report.pdf", header) == "Police Report"

    def test_empty_filename_returns_none(self):
        assert auto_classify_file("") is None

    def test_empty_content_still_checks_filename(self):
        assert auto_classify_file("witness_statement.pdf", "") == "Witness Statement"
