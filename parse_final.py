#!/usr/bin/env python3
"""
Flexible FSN10 parser with bitmap image extraction
Extracts serial number bitmap images from FSN10 files
"""
import struct
import sys
import os

def parse_date_time(date_val, time_val):
    """Parse DOS date/time format"""
    year = ((date_val >> 9) & 0x7F) + 1980
    month = (date_val >> 5) & 0x0F
    day = date_val & 0x1F
    hour = (time_val >> 11) & 0x1F
    minute = (time_val >> 5) & 0x3F
    second = (time_val & 0x1F) * 2
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"

def datetime_to_timestamp(date_val, time_val):
    """Convert DOS date/time to Unix timestamp for comparison"""
    from datetime import datetime
    year = ((date_val >> 9) & 0x7F) + 1980
    month = (date_val >> 5) & 0x0F
    day = date_val & 0x1F
    hour = (time_val >> 11) & 0x1F
    minute = (time_val >> 5) & 0x3F
    second = (time_val & 0x1F) * 2
    try:
        dt = datetime(year, month, day, hour, minute, second)
        return dt.timestamp()
    except:
        return 0

def get_version_name(ver):
    """Convert version code to year"""
    versions = {0: "1990", 1: "1999", 2: "2005", 3: "2015", 4: "2019", 5: "2020", 9999: "N/A"}
    return versions.get(ver, str(ver))

def extract_bitmap_image(image_data):
    """Extract serial number bitmap from TImageSNo structure
    
    Structure:
    - Int16 Num: number of characters
    - Int16 height, width: dimensions of each character
    - Uint16 Reserve2: reserved
    - TImgSNoData SNo[12]: 12 character bitmaps (each is Uint32 Data[32])
    
    Returns:
        dict with num, height, width, and list of character bitmaps
    """
    if len(image_data) < 8:
        return None
    
    # Parse header
    num_chars = struct.unpack_from('<h', image_data, 0)[0]
    height = struct.unpack_from('<h', image_data, 2)[0]
    width = struct.unpack_from('<h', image_data, 4)[0]
    reserve2 = struct.unpack_from('<H', image_data, 6)[0]
    
    if num_chars <= 0 or num_chars > 12 or height <= 0 or height > 32 or width <= 0 or width > 32:
        return None
    
    # Extract character bitmaps
    char_bitmaps = []
    offset = 8  # After header
    
    for char_idx in range(num_chars):
        # Each character has 32 uint32 values (columns)
        char_data = []
        for col in range(32):
            if offset + 4 <= len(image_data):
                col_data = struct.unpack_from('<I', image_data, offset)[0]
                char_data.append(col_data)
                offset += 4
            else:
                char_data.append(0)
        char_bitmaps.append(char_data)
    
    return {
        'num': num_chars,
        'height': height,
        'width': width,
        'bitmaps': char_bitmaps
    }

def bitmap_to_ascii(bitmap_data, height, width):
    """Convert bitmap data to ASCII art representation"""
    if not bitmap_data or height <= 0 or width <= 0:
        return ""
    
    lines = []
    for row in range(height):
        line = ""
        for col in range(min(width, 32)):
            if col < len(bitmap_data):
                col_data = bitmap_data[col]
                # bit31 = row 0, bit30 = row 1, etc.
                bit_pos = 31 - row
                pixel = (col_data >> bit_pos) & 1
                line += "█" if pixel else " "
            else:
                line += " "
        lines.append(line)
    return "\n".join(lines)

def save_bitmap_as_pbm(bitmap_data, height, width, filename):
    """Save bitmap as PBM (Portable Bitmap) image file"""
    try:
        with open(filename, 'w') as f:
            # PBM header
            f.write("P1\n")
            f.write(f"{width} {height}\n")
            
            # Bitmap data (1 = black, 0 = white in PBM)
            for row in range(height):
                line = ""
                for col in range(min(width, 32)):
                    if col < len(bitmap_data):
                        col_data = bitmap_data[col]
                        bit_pos = 31 - row
                        pixel = (col_data >> bit_pos) & 1
                        line += "1 " if pixel else "0 "
                    else:
                        line += "0 "
                f.write(line.strip() + "\n")
        return True
    except Exception as e:
        print(f"Error saving PBM: {e}")
        return False

def save_merged_bitmap(bitmap_info, height, width, filename):
    """Save all character bitmaps merged horizontally into single PBM file"""
    try:
        num_chars = len(bitmap_info)
        total_width = width * num_chars
        
        with open(filename, 'w') as f:
            # PBM header
            f.write("P1\n")
            f.write(f"{total_width} {height}\n")
            
            # Bitmap data - merge all characters horizontally
            for row in range(height):
                line = ""
                for char_idx, char_bitmap in enumerate(bitmap_info):
                    for col in range(min(width, 32)):
                        if col < len(char_bitmap):
                            col_data = char_bitmap[col]
                            bit_pos = 31 - row
                            pixel = (col_data >> bit_pos) & 1
                            line += "1 " if pixel else "0 "
                        else:
                            line += "0 "
                f.write(line.strip() + "\n")
        return True
    except Exception as e:
        print(f"Error saving merged PBM: {e}")
        return False

def parse_fsn10(filename, extract_images=False, output_dir=None):
    """Parse FSN10 file with optional image extraction
    
    Args:
        filename: Path to FSN10 file
        extract_images: Extract bitmap images (default: False)
        output_dir: Base directory to save extracted images (default: None)
                   Each FSN file gets its own subfolder based on filename timestamp
    
    Returns:
        List of bill records
    """
    with open(filename, 'rb') as f:
        data = f.read()
    
    HEADER_SIZE = 350
    RECORD_SIZE = 1632
    
    data_size = len(data) - HEADER_SIZE
    total_records = data_size // RECORD_SIZE
    
    if data_size % RECORD_SIZE != 0:
        print(f"WARNING: Data size {data_size} not evenly divisible by {RECORD_SIZE}")
    
    # Parse header metadata
    header = data[:HEADER_SIZE]
    head_string_2 = struct.unpack_from('<H', header, 12)[0]
    has_images = (head_string_2 == 0x2E)
    
    # Extract machine metadata from header (FSN10 extended fields)
    try:
        bank_abbr = header[26:32].decode('utf-16le', errors='ignore').rstrip('\x00').strip()  # Bank abbreviation at offset 26
        device_time = header[38:42].decode('ascii', errors='ignore').strip()  # Device enabled/activation time (YYMM) at offset 38
        machine_name = header[42:54].decode('utf-16le', errors='ignore').rstrip('\x00').strip()  # Machine name at offset 42
        machine_type = header[90:112].decode('utf-16le', errors='ignore').rstrip('\x00').strip()  # Machine type at offset 90
        machine_model_part1 = header[120:126].decode('ascii', errors='ignore').strip()  # Model part 1 at offset 120
        machine_model_part2 = header[126:148].decode('ascii', errors='ignore').strip()  # Model part 2 at offset 126
        machine_model = f"{machine_model_part1} {machine_model_part2}".strip()
        bank_code = header[276:304].decode('utf-16le', errors='ignore').rstrip('\x00').strip()  # Bank institution code at offset 276
        branch_code = header[304:332].decode('utf-16le', errors='ignore').rstrip('\x00').strip()  # Branch/outlet code at offset 304
    except Exception as e:
        bank_abbr = machine_type = machine_model = bank_code = branch_code = device_time = machine_name = ""
    
    print(f"{'='*80}")
    print(f"File: {filename}")
    print(f"{'='*80}")
    print(f"File size: {len(data):,} bytes")
    print(f"Data size: {data_size:,} bytes")
    print(f"Record size: {RECORD_SIZE} bytes")
    print(f"Total records: {total_records}")
    print(f"Has bitmap images: {'YES (0x2E)' if has_images else 'NO (0x2D)' if head_string_2 == 0x2D else f'UNKNOWN ({hex(head_string_2)})'}")
    
    # Display machine metadata if available
    if bank_abbr or machine_type or machine_model or bank_code or branch_code:
        print(f"{'-'*80}")
        print(f"Machine Metadata:")
        if bank_abbr:
            print(f"  Bank: {bank_abbr}")
        if bank_code:
            print(f"  Bank Code: {bank_code}")
        if branch_code:
            print(f"  Branch Code: {branch_code}")
        if machine_type:
            print(f"  Machine Type: {machine_type}")
        if machine_model:
            print(f"  Machine Model: {machine_model}")
        if device_time:
            print(f"  Device Time: {device_time}")
        if machine_name:
            print(f"  Machine Name: {machine_name}")
    
    print(f"{'='*80}\n")
    
    # Create output directory if needed - each FSN gets its own subfolder
    fsn_output_dir = output_dir
    if extract_images and output_dir:
        # Extract timestamp from FSN filename or use first record timestamp
        # FSN filename format: FSN10_CNY_..._YYYYMMDDHHMMSS_HM.FSN
        # The timestamp is the last 14 digits before _HM or similar suffix
        import re
        timestamp_match = re.search(r'_(\d{14})_[A-Z]+\.FSN$', os.path.basename(filename), re.IGNORECASE)
        if timestamp_match:
            fsn_timestamp = timestamp_match.group(1)
            # Format: YYYYMMDDHHMMSS -> YYYY-MM-DD_HH-MM-SS
            fsn_folder = f"{fsn_timestamp[:4]}-{fsn_timestamp[4:6]}-{fsn_timestamp[6:8]}_{fsn_timestamp[8:10]}-{fsn_timestamp[10:12]}-{fsn_timestamp[12:14]}"
        else:
            # Fallback: use base filename without extension
            fsn_folder = os.path.splitext(os.path.basename(filename))[0]
        
        fsn_output_dir = os.path.join(output_dir, fsn_folder)
        os.makedirs(fsn_output_dir, exist_ok=True)
    
    bills = []
    overall_currency_denomination_count = {}  # {currency: {denomination: count}}
    session_denomination_count = {}
    session_currency = None
    pass_count = 0
    session_record_num = 0  # Track record number within current session
    last_timestamp = None
    TIME_GAP_THRESHOLD = 3.0  # 3 seconds gap indicates new pass
    
    def print_session_summary(session_num, currency, denom_count):
        """Print summary for a counting session"""
        if not denom_count:
            return
        print(f"\n{'='*80}")
        print(f"SESSION #{session_num} SUMMARY - Currency: {currency if currency else 'N/A'}")
        print(f"{'='*80}")
        total_bills = 0
        total_value = 0
        for denom in sorted(denom_count.keys()):
            count = denom_count[denom]
            value = denom * count
            total_bills += count
            total_value += value
            print(f"  {denom:5d}¥ × {count:3d} = {value:8d}¥")
        print(f"  {'-'*30}")
        print(f"  TOTAL: {total_bills:3d} bills = {total_value:8d}¥")
        print(f"{'='*80}\n")
    
    for i in range(total_records):
        offset = HEADER_SIZE + i * RECORD_SIZE
        record_data = data[offset:offset + RECORD_SIZE]
        
        if len(record_data) < 80:
            break
        
        # Parse metadata (first 80 bytes)
        metadata = record_data[:80]
        date_val, time_val = struct.unpack_from('<HH', metadata, 0)
        
        # Detect time gaps between bills (indicates new counting session)
        current_timestamp = datetime_to_timestamp(date_val, time_val)
        if last_timestamp is not None:
            time_gap = current_timestamp - last_timestamp
            if time_gap >= TIME_GAP_THRESHOLD:
                # Print summary for previous session
                print_session_summary(pass_count, session_currency, session_denomination_count)
                
                # Start new session
                pass_count += 1
                session_denomination_count = {}
                session_currency = None
                session_record_num = 0  # Reset session record counter
                
                # Print delimiter when there's a significant time gap
                print(f"\n{'='*80}")
                print(f"  (Time gap: {time_gap:.1f}s)")
                print(f"{'='*80}\n")
        else:
            pass_count = 1
        
        session_record_num += 1  # Increment session record counter
        last_timestamp = current_timestamp
        
        tfFlag = struct.unpack_from('<H', metadata, 4)[0]
        
        # ErrorCode[3] at offset 6-11
        error_code_1, error_code_2, error_code_3 = struct.unpack_from('<HHH', metadata, 6)
        
        money_bytes = metadata[12:20]
        try:
            money_flag = money_bytes.decode('utf-16le').rstrip('\x00')
        except:
            money_flag = ""
        
        ver, valuta, char_num = struct.unpack_from('<HHH', metadata, 20)
        
        # Serial number at offset 26-51
        sno_bytes = metadata[26:52]
        try:
            # Decode and clean: remove null bytes, then remove/replace all whitespace and control chars
            sno_raw = sno_bytes.decode('utf-16le').rstrip('\x00')
            # Replace any whitespace or control characters with nothing
            sno = ''.join(c for c in sno_raw if c.isprintable() and not c.isspace())
        except:
            sno = ""
        
        # Modified MachineSNo area (bytes 52-87): FSN10 repurposes this field
        # Bytes 52-55: Error indicator (filled with '_' when serious error)
        # Bytes 56-57: Unknown flag (purpose uncertain - observed 'S' or 'M')
        error_indicator = struct.unpack_from('<HH', metadata, 52)
        unknown_flag_val = struct.unpack_from('<H', metadata, 56)[0]
        unknown_flag = chr(unknown_flag_val) if 32 <= unknown_flag_val < 127 else ''
        
        # Check if error indicator is set (0x5F5F = "__")
        has_error_indicator = (error_indicator[0] == 0x5F and error_indicator[1] == 0x5F)
        
        # Track currency for session
        if session_currency is None:
            session_currency = money_flag
        
        # Update counts
        if money_flag not in overall_currency_denomination_count:
            overall_currency_denomination_count[money_flag] = {}
        overall_currency_denomination_count[money_flag][valuta] = overall_currency_denomination_count[money_flag].get(valuta, 0) + 1
        session_denomination_count[valuta] = session_denomination_count.get(valuta, 0) + 1
        
        # Extract bitmap image (starts at byte 88, not 80!)
        # Metadata is 88 bytes: the spec's 80 bytes + 8 bytes padding/reserve
        image_section = record_data[88:]
        bitmap_info = None
        
        if extract_images:
            bitmap_info = extract_bitmap_image(image_section)
            
            if bitmap_info and fsn_output_dir:
                # Filename format: {bill_count}_{timestamp}_{denomination}_{billID}.pbm
                bill_count = i + 1  # 1-based counting
                datetime_str = parse_date_time(date_val, time_val).replace(' ', '_').replace(':', '-')
                
                # Sanitize serial number: remove whitespace, newlines, null bytes, and invalid chars
                safe_serial = ''.join(c for c in sno if c.isprintable() and c not in ' \t\n\r\0/\\:*?"<>|') if sno else f'UNKNOWN'
                if not safe_serial:  # If empty after sanitization
                    safe_serial = f'RECORD{i:03d}'
                
                # Build filename: {count}_{timestamp}_{denomination}_{serial}.pbm
                merged_filename = os.path.join(fsn_output_dir,
                                              f"{bill_count:03d}_{datetime_str}_{valuta}_{safe_serial}.pbm")
                
                # Save merged bitmap (all characters in one image)
                save_merged_bitmap(bitmap_info['bitmaps'],
                                 bitmap_info['height'],
                                 bitmap_info['width'],
                                 merged_filename)
        
        # Currency symbol mapping
        currency_symbols = {
            'CNY': '¥',
            'JPY': '¥',
            'USD': '$',
            'EUR': '€',
            'GBP': '£',
            'HKD': 'HK$',
            'AUD': 'A$',
            'CAD': 'C$',
            'RUB': '₽',
            'KRW': '₩',
        }
        currency_symbol = currency_symbols.get(money_flag, '')
        
        # Display error codes if non-zero (for fake/suspicious bills)
        error_codes_str = ""
        if tfFlag == 0 and (error_code_1 or error_code_2 or error_code_3):
            error_codes_str = f" | Err:[{error_code_1},{error_code_2},{error_code_3}]"
        
        print(f"Record #{i+1:3d} (S{pass_count}#{session_record_num:2d}): {parse_date_time(date_val, time_val)} | "
              f"{money_flag:3s} | {valuta:5d}{currency_symbol} | {get_version_name(ver):4s} | "
              f"Auth:{tfFlag}{error_codes_str} | SN: {sno:11s}")
        
        # Don't print the unknown flag since its purpose is uncertain
        # Only show error indicator when present
        if has_error_indicator:
            print(f"  Error Indicator: Set (0x5F5F)")
        
        if bitmap_info and extract_images:
            print(f"  Bitmap: {bitmap_info['num']} chars, {bitmap_info['height']}x{bitmap_info['width']} pixels")
        
        bills.append({
            'num': i+1,
            'datetime': parse_date_time(date_val, time_val),
            'currency': money_flag,
            'denomination': valuta,
            'version': get_version_name(ver),
            'authenticity': tfFlag,
            'error_codes': [error_code_1, error_code_2, error_code_3],
            'serial': sno,
            'unknown_flag': unknown_flag,
            'has_error_indicator': has_error_indicator,
            'bitmap': bitmap_info
        })
    
    # Print summary for last session
    print_session_summary(pass_count, session_currency, session_denomination_count)
    
    # Print overall summary only if there are multiple sessions
    if pass_count > 1:
        print(f"\n{'='*80}")
        print(f"OVERALL SUMMARY")
        print(f"{'='*80}")
        print(f"Total counting sessions: {pass_count}\n")
        
        grand_total_bills = 0
        grand_total_value = 0
        
        for currency in sorted(overall_currency_denomination_count.keys()):
            denom_count = overall_currency_denomination_count[currency]
            print(f"Currency: {currency if currency else 'N/A'}")
            print(f"{'-'*40}")
            
            currency_total_bills = 0
            currency_total_value = 0
            
            for denom in sorted(denom_count.keys()):
                count = denom_count[denom]
                value = denom * count
                currency_total_bills += count
                currency_total_value += value
                print(f"  {denom:5d}¥ × {count:3d} = {value:8d}¥")
            
            print(f"  {'-'*30}")
            print(f"  Subtotal: {currency_total_bills:3d} bills = {currency_total_value:8d}¥\n")
            
            grand_total_bills += currency_total_bills
            grand_total_value += currency_total_value
        
        print(f"{'='*80}")
        print(f"GRAND TOTAL: {grand_total_bills:3d} bills")
        print(f"{'='*80}\n")
    
    return bills

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Parse FSN10 files with optional bitmap image extraction',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python3 parse_final.py file.FSN                        # Parse without images
  python3 parse_final.py file.FSN --extract-images       # Extract bitmap images
  python3 parse_final.py file.FSN -e -o images/          # Extract to directory
  python3 parse_final.py file1.FSN file2.FSN -e          # Multiple files
        '''
    )
    parser.add_argument('files', nargs='+', metavar='FILE',
                        help='FSN10 file(s) to parse')
    parser.add_argument('-e', '--extract-images', action='store_true',
                        help='Extract serial number bitmap images')
    parser.add_argument('-o', '--output-dir', type=str, default='extracted_images',
                        metavar='DIR', dest='output_dir',
                        help='Output directory for extracted images (default: extracted_images)')
    
    args = parser.parse_args()
    
    for filename in args.files:
        try:
            bills = parse_fsn10(filename, 
                              extract_images=args.extract_images,
                              output_dir=args.output_dir if args.extract_images else None)
            print()
        except FileNotFoundError:
            print(f"ERROR: File not found: {filename}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"ERROR parsing {filename}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)
