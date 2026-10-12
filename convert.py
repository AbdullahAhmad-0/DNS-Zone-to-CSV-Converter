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

    # Scan the file dynamically to see what is missing
    has_ttl = any(line.strip().upper().startswith('$TTL') for line in lines)
    has_origin = any(line.strip().upper().startswith('$ORIGIN') for line in lines)
    has_soa = any('IN\tSOA' in line or 'IN SOA' in line or 'SOA' in line.split() for line in lines)
    has_ns = any('IN\tNS' in line or 'IN NS' in line or 'NS' in line.split() for line in lines)

    injected_headers = []
    
    # 1. Ask for Origin if not in file
    if not has_origin:
        origin_domain = input("Zone file is missing $ORIGIN. Enter origin domain (e.g., maahmad.com): ").strip().strip('.')
        injected_headers.append(f"$ORIGIN {origin_domain}.\n")
    else:
        # Extract origin from file dynamically to use as placeholder helper context
        origin_domain = "domain.com"
        for line in lines:
            if line.strip().upper().startswith('$ORIGIN'):
                parts = line.split()
                if len(parts) >= 2:
                    origin_domain = parts[1].strip('.')

    # 2. Ask for TTL if not in file
    if not has_ttl:
        ttl_input = input("Zone file is missing default TTL. Enter fallback value [3600]: ").strip()
        if not ttl_input:
            ttl_input = "3600"
        injected_headers.append(f"$TTL {ttl_input}\n")

    # Helper function to append a trailing dot only if it's a completely absolute domain name
    def format_absolute_host(hostname, fallback_sub, domain):
        hostname = hostname.strip()
        if not hostname:
            return f"{fallback_sub}.{domain}."
        # If it already contains a dot and doesn't end with one, treat it as an external absolute domain
        if '.' in hostname and not hostname.endswith('.'):
            return f"{hostname}."
        elif not hostname.endswith('.'):
            return f"{hostname}."
        return hostname

    # 3. Ask for SOA components if not in file
    if not has_soa:
        print("Zone file is missing an SOA record. Let's build it dynamically:")
        ns1_input = input(f"Enter Primary Name Server [ns1.{origin_domain}]: ").strip()
        ns1_val = format_absolute_host(ns1_input, "ns1", origin_domain)
            
        email_val = input(f"Enter Hostmaster Email [postmaster.{origin_domain}]: ").strip()
        if not email_val:
            email_val = f"postmaster.{origin_domain}."
        else:
            email_val = email_val.replace('@', '.')
            if not email_val.endswith('.'):
                email_val += '.'
        
        soa_record = (
            f"@   IN  SOA {ns1_val} {email_val} (\n"
            f"            2026101201 ; Serial\n"
            f"            3600       ; Refresh\n"
            f"            1800       ; Retry\n"
            f"            604800     ; Expire\n"
            f"            86400      ; Minimum TTL\n"
            f")\n"
        )
        injected_headers.append(soa_record)

    # 4. Ask for Name Servers if not in file
    if not has_ns:
        print("Zone file is missing NS records:")
        if 'ns1_val' not in locals():
            ns1_input = input(f"Enter NS1 hostname [ns1.{origin_domain}]: ").strip()
            ns1_val = format_absolute_host(ns1_input, "ns1", origin_domain)
        injected_headers.append(f"@   IN  NS  {ns1_val}\n")
        
        ns2_input = input("Enter NS2 hostname (Leave blank to skip/ignore): ").strip()
        if ns2_input:
            ns2_val = format_absolute_host(ns2_input, "ns2", origin_domain)
            injected_headers.append(f"@   IN  NS  {ns2_val}\n")

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
                        content = f'"""{content}"""'
                    
                    if priority != "":
                        csv_file.write(f"{name_str},{rdtype},{content},{priority}\n")
                    else:
                        csv_file.write(f"{name_str},{rdtype},{content}\n")
                        
    print(f"Success! CSV file created at: {csv_file_path}")

if __name__ == "__main__":
    zone_input, csv_output = get_inputs()
    convert_zone_to_csv(zone_input, csv_output)
