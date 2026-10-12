# DNS Zone to CSV Converter

This project converts a DNS zone file into a CSV file for easier inspection, import, or data processing.

It reads a zone file, repairs common missing metadata when needed, and exports records into a simple tabular format.

## What it does

The script:

- accepts a zone file path
- prompts for an output CSV filename
- detects missing `$ORIGIN`, `$TTL`, `SOA`, and `NS` records
- fills in minimal defaults when the zone file is incomplete
- parses the zone using `dnspython`
- writes DNS records to CSV

## Requirements

Install the required Python dependency:

```bash
pip install dnspython
```

## Usage

Run the script:

```bash
python convert.py
```

You will be prompted for:

1. the input zone file path/name
2. the output CSV filename

Example:

```text
Enter the path/name of your zone file (e.g., abcd.zone): abcd.zone
Enter the desired output CSV file name [output.csv]: records.csv
```

## Input zone file

The script expects a standard DNS zone file, for example:

```dns
$ORIGIN example.com.
$TTL 3600
@   IN  SOA ns1.example.com. hostmaster.example.com. (
    2026101201
    3600
    1800
    604800
    86400
)
@   IN  NS  ns1.example.com.
@   IN  A   203.0.113.10
www IN  A   203.0.113.11
mail IN MX 10 mail.example.com.
```

If the zone file is missing some required metadata, the tool can ask for values and inject them automatically.

## Output format

The generated CSV contains rows in the form:

```csv
name,type,data,priority
```

Examples:

```csv
@,A,203.0.113.10
www,A,203.0.113.11
@,MX,mail.example.com.,10
```

For `SRV` and `MX` records, the script moves the priority into a fourth CSV column.

## Record handling

The script intentionally excludes `SOA` and `NS` records from the CSV export, because they are usually used for zone metadata and delegation rather than end user record data.

Special formatting is applied for:

- `MX` records: priority is written as a separate field
- `SRV` records: priority, weight, and port are normalized
- `CNAME` records: trailing dots are stripped
- `TXT` records: quoting is simplified for CSV compatibility

## Notes

- The script uses `dns.zone.from_text()` from `dnspython` to parse zone data.
- If a file does not exist, the script will ask again until a valid path is entered.
- If the output filename does not end in `.csv`, it is automatically appended.

## Example project files

This workspace includes example zone files such as:

- `a.zone`
- `abcd.zone`

## License

This project does not currently include a formal license file.
