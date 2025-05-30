🧾 XML Comparator: WCS vs Microservice
📌 Overview
This Python tool compares XML data for orders from two different systems—WCS and Microservice—by:

Reading order ID pairs from a CSV file (orders_to_compare.csv)

Fetching corresponding XMLs from a MySQL database

Performing tag-level and attribute-level comparisons

Logging differences to a CSV file

Useful for debugging integration issues, verifying sync integrity, or comparing transformed XML structures between systems.

✅ Features
📥 Reads WCS and Microservice order_id pairs from a CSV file

🗃️ Fetches corresponding XMLs from a MySQL table named orders

🧠 Parses and flattens XMLs into structured tag-attribute-text dictionaries

🔍 Compares:

Missing tags

Extra tags

Missing or mismatched attributes

Differences in text content

XML parsing errors

📄 Saves all differences in a CSV file with clear context

📂 Input Files
orders_to_compare.csv
This file should contain rows with two columns:

wcs_order_id	micro_order_id
1001	2001
1002	2002
...	...

Each row represents a WCS and Microservice XML pair to compare.

🗃️ Database Schema
Table: orders

order_id	xml_content
1001	<order>...</order>
2001	<order>...</order>

Both WCS and Microservice XMLs are stored in the same orders table and distinguished using order_id.

🧪 Output
Creates a CSV file: order_comapare_xml_differences.csv
Each row in the file represents a detected difference.

Columns:

Order Pair (e.g., 1001-2001)

Difference Type (e.g., Text mismatch, Tag missing, Attribute mismatch)

Tag Path

Attribute (or (text))

🛠 How It Works
Read Input Pairs:
Reads WCS and Micro order ID pairs from orders_to_compare.csv.

Retrieve XMLs:
For each pair, fetches XML content from MySQL (orders table).

Parse XMLs:
Parses XMLs into element trees. Logs any parse errors.

Flatten XML:
Converts nested XML structures into tag-based dictionaries.

Compare:
Compares the structure and attributes of WCS vs Microservice XML.

Log Results:
Saves results to order_comapare_xml_differences.csv.

📦 Requirements
Python 3.8+

MySQL Server

Python Packages:
pip install mysql-connector-python
▶️ Run the Script
python compare_from_csv.py
Make sure to update the MySQL credentials in the script before running.
