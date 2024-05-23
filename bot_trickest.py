import subprocess
import json
import os
import tempfile

WORKFLOW_ID = 'ebde9ae6-0626-4ce9-90fd-7451e3818b09'
TRICKEST_TOKEN = '490987f23c1a1bf5cdbea881c5a852b637c61800'
N_MACHINES = 4

EXECUTE_CONFIG= """inputs:   # Input values for the particular workflow nodes.
  string-to-file-1.string: {DOMAINS}
  string-to-file-2.string: {SUBDOMAINS}
  3-0-google-dorks-1.string: {CSEID}
  string-input-3.string: {IPS}
  string-input-4.string: {IPRANGES}"""

def trigger_trickest_workflow(scope):
    input_file_content = EXECUTE_CONFIG.replace("{DOMAINS}", scope["domains"])
    input_file_content = input_file_content.replace("{SUBDOMAINS}", scope["subdomains"])
    input_file_content = input_file_content.replace("{CSEID}", scope["cseid"])
    input_file_content = input_file_content.replace("{IPS}", scope["ips"])
    input_file_content = input_file_content.replace("{IPRANGES}", scope["ip_ranges"])

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        # Write some data to the temporary file
        temp_file.write(input_file_content.encode('utf-8'))

        command = ["trickest-cli", "execute", "--token", TRICKEST_TOKEN, "--machines", str(N_MACHINES), "--url", f"https://trickest.io/editor/{WORKFLOW_ID}", "--config", temp_file.name]
        result = subprocess.run(command, capture_output=True, text=True)
        return extract_run_id(result.stdout)

def extract_run_id(output):
    for line in output.split('\n'):
        if 'Run successfully created!' in line:
            return line.split('ID:')[1].strip()
    return None

def get_trickest_status(run_id):
    command = ["trickest-cli", "get", "--token", TRICKEST_TOKEN, "--url", f"https://trickest.io/editor/{WORKFLOW_ID}?run={run_id}", "--json"]
    result = subprocess.run(command, capture_output=True, text=True)
    return extract_status(result.stdout, run_id)

def extract_status(output, run_id):
    data = json.loads(output)
    status_info = {
        "run_id": data.get("id", run_id),
        "status": data.get("status", "Unknown"),
        "workflow_name": data.get("workflow_name", "Unknown"),
        "started_date": data.get("started_date", "Unknown"),
        "ip_addresses": data.get("ip_addresses", [])
    }
    return status_info

def download_trickest_files(run_id, output_dir):
    nodes = [
        "1-4-domains-json-info-1",
        "1-3-subdomains-json-info-1",
        "cat-all-in-1",
        "4-0-get-initial-urls-1"
    ]
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for node in nodes:
        command = ["trickest-cli", "output", "--token", TRICKEST_TOKEN, "--url", f"https://trickest.io/editor/{WORKFLOW_ID}?run={run_id}", "--node", node, "--output-dir", output_dir]
        subprocess.run(command, capture_output=True)
