import xml.etree.ElementTree as ET
from collections import defaultdict
import os
import csv
import shutil

def parse_xml_with_lines(file_path):
    lines_by_path = {}
    # Use ET.iterparse to keep memory usage down for large files
    # and to get access to line numbers if needed, though we are not using them here.
    parser = ET.iterparse(file_path, events=("start", "end"))
    path_stack = []
    level_tag_counts = []  # One defaultdict per level

    for event, elem in parser:
        if event == "start":
            tag = elem.tag

            while len(level_tag_counts) < len(path_stack) + 1:
                level_tag_counts.append(defaultdict(int))

            count = level_tag_counts[len(path_stack)][tag]
            level_tag_counts[len(path_stack)][tag] += 1

            path_stack.append(f"{tag}[{count}]")
            full_path = "/" + "/".join(path_stack)

            lines_by_path[full_path] = {
                "attrib": dict(elem.attrib),
                "text": (elem.text.strip() if elem.text else ""),
            }
            # elem.clear() # Optional: if memory is a concern for very large XMLs

        elif event == "end":
            if path_stack:
                current_path_ending_tag = path_stack[-1].split('[')[0]
                if current_path_ending_tag == elem.tag:
                    path_stack.pop()
                    if len(level_tag_counts) > len(path_stack) + 1:
                         level_tag_counts.pop()
    return lines_by_path

def simplify_tag_path(path):
    # Extracts the tag name without the index, e.g., "OrderExtendAttribute" from "/path/to/OrderExtendAttribute[0]"
    if "/" in path:
        path = path.split("/")[-1]
    if "[" in path:
        path = path.split("[")[0]
    return path

def compare_xml_with_lines(good, bad, ignored_attrs=None):
    ignored_attrs = ignored_attrs if ignored_attrs is not None else set()
    differences = []
    handled_paths = set() # Tracks paths fully processed to avoid re-processing

    # --- Step 1 & 2: Collect and Group _ord:ProtocolData by name attribute ---
    # grouped_pd_good/bad: { parent_path -> list_of_protocol_data_items }
    # protocol_data_item: { 'path': original_full_path, 'name_attr': ..., 'text': ..., 'attrib': ... }
    grouped_pd_good = defaultdict(list)
    grouped_pd_bad = defaultdict(list)

    # Populate grouped_pd_good and add to handled_paths
    for item_path, item_data in good.items():
        if simplify_tag_path(item_path) == "_ord:ProtocolData" and 'name' in item_data.get('attrib', {}):
            parent_path = "/".join(item_path.split("/")[:-1])
            grouped_pd_good[parent_path].append({
                'path': item_path,
                'name_attr': item_data['attrib']['name'],
                'text': item_data.get('text', ''),
                'attrib': item_data['attrib']
            })
            handled_paths.add(item_path)

    # Populate grouped_pd_bad and add to handled_paths
    for item_path, item_data in bad.items():
        if simplify_tag_path(item_path) == "_ord:ProtocolData" and 'name' in item_data.get('attrib', {}):
            parent_path = "/".join(item_path.split("/")[:-1])
            grouped_pd_bad[parent_path].append({
                'path': item_path,
                'name_attr': item_data['attrib']['name'],
                'text': item_data.get('text', ''),
                'attrib': item_data['attrib']
            })
            handled_paths.add(item_path)

    # --- Step 3: Compare Grouped _ord:ProtocolData ---
    all_pd_parent_paths = set(grouped_pd_good.keys()) | set(grouped_pd_bad.keys())

    for parent_path_key in all_pd_parent_paths:
        # Convert lists to maps: { name_attr_value -> protocol_data_item }
        good_map = {pd_item['name_attr']: pd_item for pd_item in grouped_pd_good.get(parent_path_key, [])}
        bad_map = {pd_item['name_attr']: pd_item for pd_item in grouped_pd_bad.get(parent_path_key, [])}

        # Compare items in good_map against bad_map
        for name_value, good_item_data in good_map.items():
            csv_attr_identifier = f"_ord:ProtocolData[name={name_value}]"
            if name_value not in bad_map: # Missing in bad
                differences.append({
                    "Difference Type": "Tag missing in Bad", "Attribute": csv_attr_identifier,
                    "WCS Value": good_item_data['text'], "Micro Value": "", "Full Path": good_item_data['path']
                })
            else: # Present in both, compare text and other attributes
                bad_item_data = bad_map[name_value]
                if good_item_data['text'] != bad_item_data['text']:
                    differences.append({
                        "Difference Type": "Text mismatch", "Attribute": csv_attr_identifier,
                        "WCS Value": good_item_data['text'], "Micro Value": bad_item_data['text'], "Full Path": good_item_data['path']
                    })

                # Compare other attributes of this ProtocolData element (excluding 'name')
                good_item_attributes = good_item_data.get('attrib', {})
                bad_item_attributes = bad_item_data.get('attrib', {})
                for attr_key, attr_val in good_item_attributes.items():
                    if attr_key == 'name' or attr_key in ignored_attrs: continue
                    attr_id_for_csv = f"{csv_attr_identifier}/{attr_key}"
                    if attr_key not in bad_item_attributes:
                        differences.append({"Difference Type": "Attribute missing in Bad", "Attribute": attr_id_for_csv,
                                            "WCS Value": attr_val, "Micro Value": "", "Full Path": good_item_data['path']})
                    elif bad_item_attributes[attr_key] != attr_val: # Ensure bad_item_attributes[attr_key] exists
                        differences.append({"Difference Type": "Attribute mismatch", "Attribute": attr_id_for_csv,
                                            "WCS Value": attr_val, "Micro Value": bad_item_attributes[attr_key], "Full Path": good_item_data['path']})

                for attr_key, attr_val in bad_item_attributes.items(): # Check for extra attributes in bad
                    if attr_key == 'name' or attr_key in ignored_attrs: continue
                    attr_id_for_csv = f"{csv_attr_identifier}/{attr_key}"
                    if attr_key not in good_item_attributes:
                        differences.append({"Difference Type": "Extra Attribute in Bad", "Attribute": attr_id_for_csv,
                                            "WCS Value": "", "Micro Value": attr_val, "Full Path": bad_item_data['path']})

        # Check for items in bad_map not present in good_map (Extra tags in Bad)
        for name_value, bad_item_data in bad_map.items():
            if name_value not in good_map:
                csv_attr_identifier = f"_ord:ProtocolData[name={name_value}]"
                differences.append({
                    "Difference Type": "Extra Tag in Bad", "Attribute": csv_attr_identifier,
                    "WCS Value": "", "Micro Value": bad_item_data['text'], "Full Path": bad_item_data['path']
                })

    # --- Step 4: Generic Comparison for Other Elements (not _ord:ProtocolData or already handled) ---
    all_keys_from_good_or_bad = set(good.keys()) | set(bad.keys())

    for key in all_keys_from_good_or_bad:
        if key in handled_paths: # Skip if processed by ProtocolData logic
            continue

        is_in_good = key in good
        is_in_bad = key in bad
        # .get(key, {}) is important here because 'key' might be from the combined set
        # and not present in one of them if it's an add/delete.
        good_data_item = good.get(key, {})
        bad_data_item = bad.get(key, {})

        tag_name_for_csv = simplify_tag_path(key)

        if is_in_good and not is_in_bad:
            if good_data_item.get('text', '') or good_data_item.get('attrib', {}):
                differences.append({"Difference Type": "Tag missing in Bad", "Attribute": tag_name_for_csv,
                                    "WCS Value": good_data_item.get('text', ''), "Micro Value": "", "Full Path": key})
        elif not is_in_good and is_in_bad:
            if bad_data_item.get('text', '') or bad_data_item.get('attrib', {}):
                differences.append({"Difference Type": "Extra Tag in Bad", "Attribute": tag_name_for_csv,
                                    "WCS Value": "", "Micro Value": bad_data_item.get('text', ''), "Full Path": key})
        elif is_in_good and is_in_bad:
            # Attribute comparison
            good_attrs = good_data_item.get('attrib', {})
            bad_attrs = bad_data_item.get('attrib', {})
            for attr_name, good_attr_val in good_attrs.items():
                if attr_name in ignored_attrs: continue
                if attr_name not in bad_attrs:
                    differences.append({"Difference Type": "Attribute missing in Bad", "Attribute": attr_name,
                                        "WCS Value": good_attr_val, "Micro Value": "", "Full Path": key})
                elif good_attr_val != bad_attrs[attr_name]:
                    differences.append({"Difference Type": "Attribute mismatch", "Attribute": attr_name,
                                        "WCS Value": good_attr_val, "Micro Value": bad_attrs[attr_name], "Full Path": key})
            for attr_name, bad_attr_val in bad_attrs.items():
                if attr_name in ignored_attrs: continue
                if attr_name not in good_attrs:
                    differences.append({"Difference Type": "Extra Attribute in Bad", "Attribute": attr_name,
                                        "WCS Value": "", "Micro Value": bad_attr_val, "Full Path": key})

            # Text comparison
            good_text_val = good_data_item.get('text', '')
            bad_text_val = bad_data_item.get('text', '')
            if good_text_val != bad_text_val:
                if good_text_val or bad_text_val:
                    differences.append({"Difference Type": "Text mismatch", "Attribute": tag_name_for_csv,
                                        "WCS Value": good_text_val, "Micro Value": bad_text_val, "Full Path": key})

    return differences

# Assuming load_ignored_attributes and process_file_pairs are defined elsewhere in this file.
# If they are not, the test will fail with NameError.

def test_specific_xml_issue():
    # Ensure necessary imports are definitely available within this function's scope
    # if they were not top-level in the script already.
    # For robustness, assume they might not be and re-import if this function
    # were to be moved or used in a context where top-level imports are not guaranteed.
    # However, for this subtask, assume they are present at the top of xml_parser.py
    # import os
    # import csv
    # import shutil

    print("Running test_specific_xml_issue...")
    good_xml_content = """<_ord:ProcessOrder xmlns:_ord="http://example.com/ord">
    <_ord:DataArea>
        <_ord:Order>
            <_ord:OrderExtendAttribute>
                <_ord:AttributeName>ORDER_PROMO_SRC</_ord:AttributeName>
                <_ord:AttributeValue>PROMO_MS</_ord:AttributeValue>
                <_ord:AttributeType>String</_ord:AttributeType>
            </_ord:OrderExtendAttribute>
            <_ord:OrderExtendAttribute>
                <_ord:AttributeName>deliveryPhoneNumber</_ord:AttributeName>
                <_ord:AttributeValue>1234567890</_ord:AttributeValue>
                <_ord:AttributeType>String</_ord:AttributeType>
            </_ord:OrderExtendAttribute>
            <_ord:OrderExtendAttribute>
                <_ord:AttributeName>ordRewardAmt</_ord:AttributeName>
                <_ord:AttributeValue>16.98</_ord:AttributeValue>
                <_ord:AttributeType>String</_ord:AttributeType>
            </_ord:OrderExtendAttribute>
        </_ord:Order>
    </_ord:DataArea>
</_ord:ProcessOrder>"""

    bad_xml_content = """<_ord:ProcessOrder xmlns:_ord="http://example.com/ord">
    <_ord:DataArea>
        <_ord:Order>
            <_ord:OrderExtendAttribute>
                <_ord:AttributeName></_ord:AttributeName>
                <_ord:AttributeValue>PROMO_MS</_ord:AttributeValue>
                <_ord:AttributeType>String</_ord:AttributeType>
            </_ord:OrderExtendAttribute>
            <_ord:OrderExtendAttribute>
                <_ord:AttributeName>deliveryPhoneNumber</_ord:AttributeName>
                <_ord:AttributeType>String</_ord:AttributeType>
            </_ord:OrderExtendAttribute>
            <_ord:OrderExtendAttribute>
                <_ord:AttributeName>ordRewardAmt</_ord:AttributeName>
                <_ord:AttributeValue>16.98</_ord:AttributeValue>
                <_ord:AttributeType>String</_ord:AttributeType>
            </_ord:OrderExtendAttribute>
        </_ord:Order>
    </_ord:DataArea>
</_ord:ProcessOrder>"""

    # Use a unique name for the test directory, possibly including a timestamp or random element if running in parallel
    # For this case, a fixed name is fine, with robust cleanup.
    test_base_dir = "temp_xml_test_data_unique"
    xml_files_subdir = "xml_files" # subdirectory for xml files as expected by process_file_pairs

    # Construct full paths
    current_script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else '.'
    test_base_abs_path = os.path.join(current_script_dir, test_base_dir)
    xml_files_abs_path = os.path.join(test_base_abs_path, xml_files_subdir)

    # Ensure clean slate for test directory
    if os.path.exists(test_base_abs_path):
        shutil.rmtree(test_base_abs_path)
    os.makedirs(xml_files_abs_path, exist_ok=True)

    good_xml_filename = "good_test.xml"
    bad_xml_filename = "bad_test.xml"
    good_xml_file_path = os.path.join(xml_files_abs_path, good_xml_filename)
    bad_xml_file_path = os.path.join(xml_files_abs_path, bad_xml_filename)

    file_pairs_csv_path = os.path.join(test_base_abs_path, "test_file_pairs.csv")
    ignore_csv_path = os.path.join(test_base_abs_path, "test_ignore_attributes.csv")

    with open(good_xml_file_path, "w", encoding="utf-8") as f:
        f.write(good_xml_content)
    with open(bad_xml_file_path, "w", encoding="utf-8") as f:
        f.write(bad_xml_content)

    with open(file_pairs_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["wcs_file", "micro_file"])
        writer.writerow([os.path.splitext(good_xml_filename)[0], os.path.splitext(bad_xml_filename)[0]])

    with open(ignore_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Attribute"])

    # Calls to actual functions are expected here.
    # If load_ignored_attributes or process_file_pairs are not defined in the script,
    # this test will raise a NameError.
    ignored_attributes_set = load_ignored_attributes(ignore_csv_path)
    actual_diffs = process_file_pairs(input_csv=file_pairs_csv_path, xml_folder=xml_files_abs_path, ignored_attrs=ignored_attributes_set)

    expected_diffs = [
       {
           "Difference Type": "Text mismatch",
           "Attribute": "_ord:AttributeName",
           "WCS Value": "ORDER_PROMO_SRC",
           "Micro Value": "",
           "Full Path": "/_ord:ProcessOrder[0]/_ord:DataArea[0]/_ord:Order[0]/_ord:OrderExtendAttribute[0]/_ord:AttributeName[0]"
       },
       {
           "Difference Type": "Tag missing in Bad",
           "Attribute": "_ord:AttributeValue",
           "WCS Value": "1234567890",
           "Micro Value": "",
           "Full Path": "/_ord:ProcessOrder[0]/_ord:DataArea[0]/_ord:Order[0]/_ord:OrderExtendAttribute[1]/_ord:AttributeValue[0]"
       }
    ]

    def compare_lists_of_dicts_order_insensitive(list1, list2):
        if len(list1) != len(list2):
            print(f"Length mismatch: expected {len(list2)}, got {len(list1)}")
            return False

        s_list1 = sorted([str(sorted(d.items())) for d in list1])
        s_list2 = sorted([str(sorted(d.items())) for d in list2])

        if s_list1 == s_list2:
            return True
        else:
            print("Difference details (sorted string representations):")
            # print(f"Expected: {s_list2}") # Can be very verbose
            # print(f"Actual:   {s_list1}")
            set1 = {frozenset(d.items()) for d in list1}
            set2 = {frozenset(d.items()) for d in list2}
            missing_in_actual = [dict(fs) for fs in set2 - set1]
            extra_in_actual = [dict(fs) for fs in set1 - set2]
            if missing_in_actual:
                print(f"Items in expected but not actual: {missing_in_actual}")
            if extra_in_actual:
                print(f"Items in actual but not expected: {extra_in_actual}")
            return False

    test_passed = compare_lists_of_dicts_order_insensitive(actual_diffs, expected_diffs)

    if test_passed:
        print("Test PASSED!")
    else:
        print("Test FAILED!")
        # Detailed printout already handled by the comparison function if it fails

    # Cleanup
    try:
        shutil.rmtree(test_base_abs_path)
        print(f"Cleaned up temporary directory: {test_base_abs_path}")
    except OSError as e:
        print(f"Error cleaning up {test_base_abs_path}: {e}")

    return test_passed

def test_protocol_data_comparison():
    print("Running test_protocol_data_comparison...")
    # Define Good XML Content
    good_xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<_ord:PaymentInstruction xmlns:_ord="http://www.ibm.com/xmlns/prod/commerce/9/order" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" paymentMethodName="PayPal">
    <_ord:Amount>9.09</_ord:Amount>
    <_ord:BillingAddressId>12345</_ord:BillingAddressId>
    <_ord:Description>Order 0001133444 payment through PayPal</_ord:Description>
    <_ord:PayMethodId>PayPal</_ord:PayMethodId>
    <_ord:PaymentRule type="IMMEDIATE">ON_ORDER_SUBMISSION</_ord:PaymentRule>
    <_ord:PolicyId>10001</_ord:PolicyId>
    <_ord:ProtocolData name="payment_token">good_token_value</_ord:ProtocolData>
    <_ord:ProtocolData name="payer_id">good_payer_id</_ord:ProtocolData>
    <_ord:ProtocolData name="correlation_id">good_correlation_id</_ord:ProtocolData>
    <_ord:ProtocolData name="billto_stateprovince">CA</_ord:ProtocolData>
    <_ord:ProtocolData name="CreditCardCVV2Code"></_ord:ProtocolData>
    <_ord:ProtocolData name="ExpiryDate">12/2025</_ord:ProtocolData>
    <_ord:ProtocolData name="extra_in_good">This is only in good XML</_ord:ProtocolData>
    <_ord:ProtocolData name="mismatch_text">TextInGood</_ord:ProtocolData>
    <_ord:SequenceNumber>0</_ord:SequenceNumber>
    <_ord:XMLPayExtData name="PaymentExtData">PayPal</_ord:XMLPayExtData>
    <UserData>
        <UserArea/>
    </UserData>
</_ord:PaymentInstruction>
"""
    # Define Bad XML Content
    bad_xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<_ord:PaymentInstruction xmlns:_ord="http://www.ibm.com/xmlns/prod/commerce/9/order" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" paymentMethodName="PayPal">
    <_ord:Amount>9.09</_ord:Amount>
    <_ord:BillingAddressId>12345</_ord:BillingAddressId>
    <_ord:Description>Order 0001133444 payment through PayPal</_ord:Description>
    <_ord:PayMethodId>PayPal</_ord:PayMethodId>
    <_ord:PaymentRule type="IMMEDIATE">ON_ORDER_SUBMISSION</_ord:PaymentRule>
    <_ord:PolicyId>10001</_ord:PolicyId>
    <_ord:ProtocolData name="payment_token">good_token_value</_ord:ProtocolData>
    <_ord:ProtocolData name="payer_id">good_payer_id</_ord:ProtocolData>
    <_ord:ProtocolData name="correlation_id">good_correlation_id</_ord:ProtocolData>
    <_ord:ProtocolData name="CreditCardCVV2Code"></_ord:ProtocolData>
    <_ord:ProtocolData name="ExpiryDate">12/2025</_ord:ProtocolData>
    <_ord:ProtocolData name="extra_in_bad">This is only in bad XML</_ord:ProtocolData>
    <_ord:ProtocolData name="mismatch_text">TextInBad</_ord:ProtocolData>
    <_ord:SequenceNumber>0</_ord:SequenceNumber>
    <_ord:XMLPayExtData name="PaymentExtData">PayPal</_ord:XMLPayExtData>
    <UserData>
        <UserArea/>
    </UserData>
</_ord:PaymentInstruction>
"""

    test_base_dir = "temp_protocol_data_test"
    xml_files_subdir = "xml_files"
    current_script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else '.'
    test_base_abs_path = os.path.join(current_script_dir, test_base_dir)
    xml_files_abs_path = os.path.join(test_base_abs_path, xml_files_subdir)

    if os.path.exists(test_base_abs_path):
        shutil.rmtree(test_base_abs_path)
    os.makedirs(xml_files_abs_path, exist_ok=True)

    good_xml_filename = "good_pd_test.xml"
    bad_xml_filename = "bad_pd_test.xml"
    good_xml_file_path = os.path.join(xml_files_abs_path, good_xml_filename)
    bad_xml_file_path = os.path.join(xml_files_abs_path, bad_xml_filename)

    file_pairs_csv_path = os.path.join(test_base_abs_path, "test_pd_file_pairs.csv")
    ignore_csv_path = os.path.join(test_base_abs_path, "test_pd_ignore_attributes.csv")

    with open(good_xml_file_path, "w", encoding="utf-8") as f:
        f.write(good_xml_content)
    with open(bad_xml_file_path, "w", encoding="utf-8") as f:
        f.write(bad_xml_content)

    with open(file_pairs_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["wcs_file", "micro_file"])
        writer.writerow([os.path.splitext(good_xml_filename)[0], os.path.splitext(bad_xml_filename)[0]])

    with open(ignore_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Attribute"]) # Empty ignore file, just header

    ignored_attributes_set = load_ignored_attributes(ignore_csv_path)
    # Assuming process_file_pairs is defined in the script and uses parse_xml_with_lines & compare_xml_with_lines
    actual_diffs = process_file_pairs(input_csv=file_pairs_csv_path, xml_folder=xml_files_abs_path, ignored_attrs=ignored_attributes_set)

    expected_diffs = [
        {
            "Difference Type": "Tag missing in Bad",
            "Attribute": "_ord:ProtocolData[name=billto_stateprovince]",
            "WCS Value": "CA", "Micro Value": "",
            "Full Path": "/_ord:PaymentInstruction[0]/_ord:ProtocolData[3]"
        },
        {
            "Difference Type": "Tag missing in Bad",
            "Attribute": "_ord:ProtocolData[name=extra_in_good]",
            "WCS Value": "This is only in good XML", "Micro Value": "",
            "Full Path": "/_ord:PaymentInstruction[0]/_ord:ProtocolData[6]"
        },
        {
            "Difference Type": "Extra Tag in Bad",
            "Attribute": "_ord:ProtocolData[name=extra_in_bad]",
            "WCS Value": "", "Micro Value": "This is only in bad XML",
            # Path from bad XML's perspective, careful with indices if they differ
            "Full Path": "/_ord:PaymentInstruction[0]/_ord:ProtocolData[5]"
        },
        {
            "Difference Type": "Text mismatch",
            "Attribute": "_ord:ProtocolData[name=mismatch_text]",
            "WCS Value": "TextInGood", "Micro Value": "TextInBad",
            "Full Path": "/_ord:PaymentInstruction[0]/_ord:ProtocolData[7]"
        }
    ]

    # Helper for order-insensitive comparison of lists of dictionaries
    def compare_lists_of_dicts_order_insensitive(list1, list2):
        if len(list1) != len(list2):
            print(f"Length mismatch: expected {len(list2)}, got {len(list1)}")
            print(f"Actual Diffs: {list1}")
            print(f"Expected Diffs: {list2}")
            return False

        s_list1 = sorted([str(sorted(d.items())) for d in list1])
        s_list2 = sorted([str(sorted(d.items())) for d in list2])

        if s_list1 == s_list2:
            return True
        else:
            print("Difference details:")
            set1 = {frozenset(d.items()) for d in list1}
            set2 = {frozenset(d.items()) for d in list2}

            missing_in_actual = [dict(fs) for fs in set2 - set1]
            if missing_in_actual:
                print(f"Items in expected but not actual: {missing_in_actual}")

            extra_in_actual = [dict(fs) for fs in set1 - set2]
            if extra_in_actual:
                print(f"Items in actual but not expected: {extra_in_actual}")
            return False

    test_passed = compare_lists_of_dicts_order_insensitive(actual_diffs, expected_diffs)

    if test_passed:
        print("Test PASSED! (test_protocol_data_comparison)")
    else:
        print("Test FAILED! (test_protocol_data_comparison)")

    try:
        shutil.rmtree(test_base_abs_path)
        print(f"Cleaned up temporary directory: {test_base_abs_path}")
    except OSError as e:
        print(f"Error cleaning up {test_base_abs_path}: {e}")

    return test_passed
