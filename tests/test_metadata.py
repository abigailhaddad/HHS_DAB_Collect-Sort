"""Header parsing across the four template generations the corpus spans."""
import metadata

GRANT_APPEALS_1978 = (
    "DEPARTI1ENTAL GRANT APPEALS BOARD\nDepartment of Health, Education, and "
    "Welfare\nSUBJECT: Topeka Public Schools, Topeka, Kansas\nDocket Nos. 77-7, "
    "77-8, and 77-9\nDecision No. 47\nDATE~ SEP. 28, 1978\nDECISION")
APPELLATE_1993 = (
    "Department of Health and Human Services\nDEPARTMENTAL APPEALS BOARD\n"
    "Appellate Division\nIn the Case of:\nTajammul H. Bhatti, M.D.,\nPetitioner,\n"
    "- v. -\nThe Inspector General.\nDATE: June 1, 1993\nDocket No. C-92-045\n"
    "Decision No. 1415\n")
CIVIL_REMEDIES_2008 = (
    "Department of Health and Human Services\nDEPARTMENTAL APPEALS BOARD\n"
    "Civil Remedies Division\nIn the Case of:\nDaniel M. Stewart,\nPetitioner,\n"
    "- v. -\nCenters for Medicare & Medicaid Services.\nDate: January 9, 2008\n"
    "Docket No. C-07-429\nDecision No. CR1723\n")
BARE_DATE_2015 = (
    "Department of Health and Human Services\nDEPARTMENTAL APPEALS BOARD\n"
    "Appellate Division\nWilliam Smith, Sr. Tri-County Child Development "
    "Council, Inc.\nDocket No. A-15-44\nDecision No. 2647\nJune 30, 2015\nDECISION")


def test_grant_appeals_board():
    m = metadata.parse(GRANT_APPEALS_1978)
    assert m["decision_no"] == "47"
    assert m["decision_date"] == "1978-09-28"       # "DATE~ SEP. 28, 1978"
    assert m["tribunal"] == "Grant Appeals Board"
    assert m["docket_nos"] == ["77-7", "77-8", "77-9"]


def test_appellate_division():
    m = metadata.parse(APPELLATE_1993)
    assert (m["decision_no"], m["decision_date"]) == ("1415", "1993-06-01")
    assert m["tribunal"] == "Appellate Division"
    assert m["respondent"] == "Inspector General"


def test_civil_remedies_division():
    m = metadata.parse(CIVIL_REMEDIES_2008)
    assert (m["decision_no"], m["decision_date"]) == ("CR1723", "2008-01-09")
    assert m["tribunal"] == "Civil Remedies Division"
    assert m["respondent"] == "CMS"


def test_bare_date_line():
    m = metadata.parse(BARE_DATE_2015)
    assert (m["decision_no"], m["decision_date"]) == ("2647", "2015-06-30")


def test_year_comes_from_the_text_not_the_filename():
    # Filenames are hand-typed and carry real typos: "0980.02.25DAB083".
    m = metadata.parse("Decision No. 83\nDATE: February 25, 1980\n",
                       "0980.02.25DAB083 New Mexico Human Services Department")
    assert m["year"] == 1980
    assert m["filename_year"] == 980


def test_filename_year_is_the_fallback_when_no_date_parses():
    m = metadata.parse("A decision with no parseable date line.",
                       "1994.05.02DAB1450 Some Grantee")
    assert m["decision_date"] is None
    assert m["year"] == 1994


def test_missing_fields_come_back_none_not_empty_string():
    m = metadata.parse("Nothing resembling a decision header.")
    assert m["decision_no"] is None
    assert m["tribunal"] is None
    assert m["docket_nos"] == []


def test_ig_abbreviation_does_not_match_the_bare_word_ig():
    # "\\bI\\.?G\\.?\\b" under IGNORECASE matches "ig" in ordinary text.
    m = metadata.parse("Civil Remedies Division\nThe petitioner ran a big rig "
                       "repair shop and ig is not an abbreviation here.\n")
    assert m["respondent"] != "Inspector General"


def test_docket_separator_is_case_insensitive():
    # re.split does not inherit the pattern's IGNORECASE flag.
    m = metadata.parse("Civil Remedies Division\nDocket Nos. 84-228 AND 84-229\n")
    assert m["docket_nos"] == ["84-228", "84-229"]


def test_docket_run_with_oxford_comma():
    m = metadata.parse("Docket Nos. 77-7, 77-8, and 77-9\n")
    assert m["docket_nos"] == ["77-7", "77-8", "77-9"]


def test_garbled_date_label_yields_none_not_a_fact_date():
    # DAB No. 33: "DATE: ~E.rch 3, 1977" would not parse, and the fall-through
    # picked "Feburary 1, 1969" out of the statement of facts.
    text = ("DEPARTMENTAL GRANT APPEALS BOARD\nDecision No. 33\n"
            "DATE: @@@@ 3, 1977\nDECISION\nThis is a review of expenditure "
            "disallowances for the period from February 1, 1969 through 1973.")
    m = metadata.parse(text, "1977.03.03 DAB033 Lane County")
    assert m["decision_date"] != "1969-02-01"
    assert m["year"] == 1977           # from the filename, which is right here


def test_ocr_damaged_month_names_still_parse():
    for raw, want in (("Nay 29, 1981", "1981-05-29"),
                      ("Harch 14, 1977", "1977-03-14"),
                      ("August 14 I 1978", "1978-08-14"),
                      ("October 31 1978", "1978-10-31")):
        m = metadata.parse(f"Appellate Division\nDATE: {raw}\n")
        assert m["decision_date"] == want, raw


def test_a_dangling_connective_is_not_a_docket():
    # DAB No. 628: "...$11,881,983 in Docket No.\n84-228, and $1,032,130 in
    # Docket No. 85-25." The run ended on "and", which became a docket number.
    m = metadata.parse("HCFA disallowed $11,881,983 in Docket No.\n84-228, and "
                       "$1,032,130 in Docket No. 85-25.\n")
    assert m["docket_nos"] == ["84-228"]
