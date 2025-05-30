xmldiffpointer


xmldiffpointer is a Python script designed to compare XML data from two MySQL tables — one from a legacy WebSphere Commerce (WCS) system and the other from a new Microservice-based system. Its purpose is to validate functional parity by identifying differences in structure and content between the two XML outputs.

🚀 Features
✅ Connects to a MySQL database and retrieves XML data from two tables: wcs and micro
✅ Parses XML strings into element trees using xml.etree.ElementTree
✅ Flattens XML into dictionaries of tags, attributes, and text
✅ Compares:

Missing tags

Extra tags

Missing or mismatched attributes

Differences in text content

✅ Records differences with clear context (tag path, attribute, type)
✅ Outputs results to a CSV file (order_comapare_xml_differences.csv)

🛠 How It Works
Data Retrieval
Reads order ID pairs from orders_to_compare.csv, then fetches the XML for each order ID from a single orders table (with rows representing both WCS and Microservice orders).

XML Parsing
Uses ElementTree to parse XML strings into trees.

Flattening XML
Recursively converts each XML tree into a structure mapping tag names to lists of their attributes and text content.

Comparison Logic
For each pair:

Checks if tags exist in both XMLs

Compares attributes and values

Detects missing, extra, or mismatched tags, attributes, and text

Result Logging
Differences are saved in order_comapare_xml_differences.csv with columns:

Difference Type

Tag Path

Attribute

Order Pair
