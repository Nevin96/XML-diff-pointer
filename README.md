# XML Comparator for WCS and Microservice Tables

## 📌 Overview

This project compares XML data from two MySQL tables: `wcs` and `microservice`. Each table contains 15 XML records, and the program performs a **pairwise comparison**—comparing the first XML in `wcs` with the first in `microservice`, the second with the second, and so on.

It helps identify differences in structure, content, or values between corresponding XML entries in both systems.

---

🚀 Features
✅ Connects to a MySQL database and retrieves XML data from two tables: wcs and micro.
✅ Parses XML strings into element trees.
✅ Flattens XML trees into dictionaries of tags and their attributes/text.
✅ Compares:
Missing tags
Extra tags
Missing or mismatched attributes
Text content differences
✅ Records the differences with context (tag path, attribute name, difference type).
✅ Outputs the comparison results to a CSV file (diff15.csv) with a row per difference and pair index.

🛠 How It Works
Data Retrieval:
Fetches XML data (up to 15 records by default) from both wcs and micro tables using mysql.connector.

XML Parsing:
Converts XML strings to element trees using xml.etree.ElementTree.

Flattening XML:
Recursively flattens each XML tree into a structure of tags with a list of associated attributes and text.

Comparison Logic:
For each tag and index in WCS XML, checks for:
Missing counterparts in microservice XML.
Differences in attribute values.
Differences in text content.

Detects extra tags present only in microservice XML.

Result Logging:Writes differences into a CSV with columns: Pair Index, Difference Type, Tag Path, and Attribute.
