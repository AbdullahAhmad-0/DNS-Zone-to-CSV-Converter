import os
import sys

# Ensure dnspython is installed
try:
    import dns.zone
    import dns.rdatatype
except ImportError:
    print("Error: The 'dnspython' library is required.")
    print("Please run: pip install dnspython")
    sys.exit(1)

def get_inputs():
    while True:
        zone_file = input("Enter the path/name of your zone file (e.g., abcd.zone): ").strip()
        if os.path.exists(zone_file):
            break
        print(f"Error: File '{zone_file}' not found. Please try again.")
    
    csv_file = input("Enter the desired output CSV file name [output.csv]: ").strip()
    if not csv_file:
        csv_file = "output.csv"
    if not csv_file.lower().endswith('.csv'):
        csv_file += '.csv'
        
    return zone_file, csv_file

def preprocess_and_load_zone(zone_file_path):
    with open(zone_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    has_ttl = any(line.strip().upper().startswith('$TTL') for line in lines)
    has_origin = any(line.strip().upper().startswith('$ORIGIN') for line in lines)
    has_soa = any('IN\tSOA' in line or 'IN SOA' in line or 'SOA' in line.split() for line in lines)
    has_ns = any('IN\tNS' in line or 'IN NS' in line or 'NS' in line.split() for line in lines)

    injected_headers = []
    origin_domain = "maahmad.com"

    if not has_origin:
        injected_headers.append(f"$ORIGIN {origin_domain}.\n")
    if not has_ttl:
        injected_headers.append("$TTL 3600\n")
    if not has_soa:
        injected_headers.append(f"@   IN  SOA ns1.{origin_domain}. postmaster.{origin_domain}. ( 2026101201 3600 1800 604800 86400 )\n")
    if not has_ns:
        injected_headers.append(f"@   IN  NS  ns1.{origin_domain}.\n")

    complete_zone_text = "".join(injected_headers) + "".join(lines)
    return dns.zone.from_text(complete_zone_text, origin=origin_domain, relativize=False)

def convert_zone_to_csv(zone_file_path, csv_file_path):
    print(f"Analyzing and loading zone file: {zone_file_path}")
    try:
        zone = preprocess_and_load_zone(zone_file_path)
    except Exception as e:
        print(f"An error occurred while parsing the zone file: {e}")
        return

    print("Parsing records and structuring for Bulk Importer...")
    
    with open(csv_file_path, mode='w', encoding='utf-8') as csv_file:
        for name, node in zone.nodes.items():
            name_str = name.relativize(zone.origin).to_text()
            if name_str == "@" or name_str == "":
                name_str = "@"
                
            for rdataset in node.rdatasets:
                rdtype = dns.rdatatype.to_text(rdataset.rdtype)
                
                if rdtype in ['SOA', 'NS']:
                    continue
                
                for rdata in rdataset:
                    content = rdata.to_text(origin=zone.origin, relativize=False)
                    priority = ""
                    
                    if rdtype == 'SRV':
                        parts = content.split(' ', 3)
                        if len(parts) >= 4:
                            priority = parts[0]
                            weight = parts[1]
                            port = parts[2]
                            target = parts[3].rstrip('.')
                            content = f"{weight} {port} {target}"
                    
                    elif rdtype == 'MX':
                        parts = content.split(' ', 1)
                        if len(parts) == 2:
                            priority = parts[0]
                            content = parts[1].rstrip('.')
                            
                    elif rdtype == 'CNAME':
                        content = content.rstrip('.')
                        
                    elif rdtype == 'TXT':
                        content = content.replace('" "', '').replace('""', '')
                        if content.startswith('"') and content.endswith('"'):
                            content = content[1:-1]
                        # Wraps inside standard triple-escaped quotes instead of backslashes
                        content = f'"""{content}"""'
                    
                    if priority != "":
                        csv_file.write(f"{name_str},{rdtype},{content},{priority}\n")
                    else:
                        csv_file.write(f"{name_str},{rdtype},{content}\n")
                        
    print(f"Success! CSV file created at: {csv_file_path}")

if __name__ == "__main__":
    zone_input, csv_output = get_inputs()
    convert_zone_to_csv(zone_input, csv_output)
