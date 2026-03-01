# Julong FSN10 File Parser (聚龙FTP协议 人民银行2018 FSN)

A Python parser for FSN10 (Financial Serial Number) format files used in Chinese currency validation systems.

## Overview

This parser successfully reads and validates FSN10 format files containing currency validation records, extracting information such as serial numbers, denominations, authenticity flags, timestamps, and machine identification.

**Note:** This implementation is based on reverse engineering of actual FSN10 files. The format appears to be an extended/evolved version of the official "银行现金处理设备冠字号码查询管理数据格式" specification. Key differences include:
- Extended header (350 bytes vs. spec's ~32 bytes)
- HeadString[1] = 2 (indicating FSN10 format) vs. spec's value of 1
- Modified record structure (88 bytes metadata vs. spec's 100 bytes)
- Different field layouts and sizes compared to the original specification

## FSN10 File Format

### Header Structure (350 bytes)

**FSN10 Extended Format** - differs from original specification

| Offset | Size | Field | Type | Value/Description |
|--------|------|-------|------|-------------------|
| 0-3 | 4 bytes | HeadStart | byte[4] | `{20, 10, 7, 26}` - File signature (matches spec) |
| 4 | 1 byte | HeadString[0] | byte | `0` (matches spec) |
| 5 | 1 byte | HeadString[1] | byte | `2` - FSN10 format version (spec says 1) |
| 6 | 2 bytes | HeadString[2] | uint16 | `0x2E` = has images, `0x2D` = no images (matches spec) |
| 8-13 | 6 bytes | HeadString[3-8] | char[6] | `'S', 'N', 'o', ...` - Format identifier (matches spec) |
| 14-25 | 12 bytes | Unknown | - | Purpose unknown |
| 26-31 | 6 bytes | BankAbbr | UTF-16LE | Bank abbreviation (e.g., "CCB" or "BOC") |
| 32-37 | 6 bytes | Unknown | - | Purpose unknown |
| 38-41 | 4 bytes | DeviceTime | ASCII | Device enabled/activation time (YYMM format) |
| 42-53 | 12 bytes | MachineName | UTF-16LE | Machine name/identifier |
| 54-89 | 36 bytes | Unknown | - | Purpose unknown |
| 90-111 | 22 bytes | MachineType | UTF-16LE | Machine type identifier |
| 112-119 | 8 bytes | Unknown | - | Purpose unknown |
| 120-125 | 6 bytes | ModelPart1 | ASCII | Machine model part 1 |
| 126-147 | 22 bytes | ModelPart2 | ASCII | Machine model part 2 with details |
| 148-275 | 128 bytes | Unknown | - | Purpose unknown |
| 276-303 | 28 bytes | BankCode | UTF-16LE | Bank/financial institution code |
| 304-331 | 28 bytes | BranchCode | UTF-16LE | Branch/outlet code |
| 332-341 | 10 bytes | Unknown | - | Purpose unknown |
| 342-345 | 4 bytes | HeadEnd | byte[4] | `{0, 1, 2, 3}` - End marker (matches spec) |
| 346-349 | 4 bytes | Padding | - | Additional padding (not in original spec) |

**Note:** Original spec defines a 32-byte header. FSN10 format extends this to 350 bytes with machine/bank metadata.

### Record Structure (1632 bytes per record)

Each record contains metadata and image data:

#### Part 1: Metadata (88 bytes) - TKFSN_Record_File

| Offset | Size | Field | Type | Description |
|--------|------|-------|------|-------------|
| 0-1 | 2 bytes | Date | uint16 | Date in DOS format (matches spec) |
| 2-3 | 2 bytes | Time | uint16 | Time in DOS format (matches spec) |
| 4-5 | 2 bytes | tfFlag | uint16 | Authenticity: 0=fake, 1=genuine, 2=damaged, 3=old (matches spec) |
| 6-11 | 6 bytes | ErrorCode | uint16[3] | Error codes per spec (not used in observed files) |
| 12-19 | 8 bytes | MoneyFlag | uint16[4] | Currency code (UTF-16LE, e.g., "CNY", "HKD") (matches spec) |
| 20-21 | 2 bytes | Ver | uint16 | Version code (0-5, 9999) (matches spec) |
| 22-23 | 2 bytes | Valuta | uint16 | Denomination (matches spec) |
| 24-25 | 2 bytes | CharNUM | uint16 | Number of serial number characters (matches spec) |
| 26-51 | 26 bytes | SNo | uint16[13] | Serial number (UTF-16LE, differs from spec's 12-element array) |
| 52-55 | 4 bytes | ErrorIndicator | uint16[2] | Error indicator (filled with '_' 0x5F when serious errors occur) |
| 56-57 | 2 bytes | Unknown Flag | uint16 | **Purpose uncertain** - Observed values: 'S' (0x53) or 'M' (0x4D) |
| 58-87 | 30 bytes | Reserved | - | Padding/reserved (all zeros observed) |

**Note on Unknown Flag (offset 56-57):**
- **Purpose not confirmed** - interpretation uncertain
- Observed to change from 'S' to 'M' within a single counting session
- Does NOT appear to indicate the machine's counting mode setting (单次模式 vs 累加模式)
- May be a per-record state indicator, but exact meaning requires further investigation

**Note:** FSN10 metadata is 88 bytes vs. spec's 100 bytes (excluding ImageSNo). Field layout has been modified from original specification.

**DOS Date Format (uint16):**
- Bits 15-9: Year offset from 1980 (0-127)
- Bits 8-5: Month (1-12)
- Bits 4-0: Day (1-31)

**DOS Time Format (uint16):**
- Bits 15-11: Hours (0-23)
- Bits 10-5: Minutes (0-59)
- Bits 4-0: Seconds / 2 (0-29)

#### Part 2: Image Data (1544 bytes) - TImageSNo

| Offset | Size | Field | Type | Description |
|--------|------|-------|------|-------------|
| 88-89 | 2 bytes | Num | int16 | Number of characters (typically 8-10) |
| 90-91 | 2 bytes | height | int16 | Character height in pixels (e.g., 32) |
| 92-93 | 2 bytes | width | int16 | Character width in pixels (e.g., 24, 32) |
| 94-95 | 2 bytes | Reserve2 | uint16 | Purpose unknown (reverse-engineered) |
| 96-1631 | 1536 bytes | SNo[12] | TImgSNoData[12] | 12 character bitmaps (128 bytes each) |

**TImgSNoData Structure (128 bytes per character):**
- 32 × uint32 (4 bytes each)
- Each uint32 represents one vertical column of pixels
- Bit layout: bit 31 = row 0 (top), bit 30 = row 1, ..., bit 0 = row 31 (bottom)
- Column-major format: columns are stored sequentially

### Version Code Mapping

| Code | Edition Year | Description |
|------|-------------|-------------|
| 0 | 1990 | 1990 edition RMB (per spec) |
| 1 | 1999 | 1999 edition RMB (per spec) |
| 2 | 2005 | 2005 edition RMB (per spec) |
| 3 | 2015 | 2015 edition RMB (extended, not in original spec) |
| 4 | 2019 | 2019 edition RMB (extended, not in original spec) |
| 5 | 2020 | 2020 edition RMB (extended, not in original spec) |
| 9999 | N/A | Unknown/Not applicable (per spec for non-RMB currencies) |

### Authenticity Flag Values

| Value | Status | Description |
|-------|--------|-------------|
| 0 | Unverified/Suspicious | Machine could not verify authenticity (per spec: 假币或可疑币)<br/>**Note:** Does NOT necessarily mean counterfeit - often genuine bills that machine cannot recognize |
| 1 | Genuine | Authenticated bill (per spec: 真币) |
| 2 | Damaged | Damaged but genuine (per spec: 残币, for sorting machines) |
| 3 | Old | Old edition, still valid (per spec: 旧币, for sorting machines) |

### Error Codes (ErrorCode[3])

When bills cannot be verified (tfFlag=0), error codes indicate the reason:
- **Spec defines**: Valid codes 1-12 representing specific detection issues
- **Verified bills (tfFlag=1)**: All three set to 0
- **FSN10 implementation**: Uses non-standard encoding (not spec's 1-12 range)

**Common error codes observed in FSN10:**
- `[0x5555, 0x5555, 0x8005]` (decimal: [21845, 21845, 32773]) - Detection issues:
  - 重张 (double sheet detection)
  - When denomination = 0: 面额识别异常 E910 (denomination recognition error)
- `[0x5555, 0x5555, 0x800D]` (decimal: [21845, 21845, 32781]) - Similar detection issues
- `[0x55D5, 0x5555, 0x8005]` (decimal: [21973, 21845, 32773]) - 磁异常 (magnetic anomaly)

**Error Indicator Field (bytes 52-55):**
When serious errors occur during counting, this field is filled with underscores (0x5F5F = "__"):
- Indicates the machine encountered an error during processing
- Often correlates with denomination = 0 and Auth = 0
- Machine-reported error codes (like E910) correspond to specific combinations of these internal codes

**Important:** Error codes indicate machine detection issues, not proof of counterfeit bills. Genuine bills may trigger errors due to wear, folding, or machine limitations.

## Usage

### Parse a single file (metadata only):
```bash
python3 parse_final.py <fsn_file>
```

### Parse with bitmap image extraction:
```bash
python3 parse_final.py <fsn_file> --extract-images
```

### Extract images to specific directory:
```bash
python3 parse_final.py <fsn_file> -e -o output_directory/
```

### Parse multiple files:
```bash
python3 parse_final.py file1.FSN file2.FSN file3.FSN --extract-images
```

### Examples:
```bash
# Basic parsing (no image extraction)
python3 parse_final.py sample_file.FSN

# Extract bitmap images to default directory (extracted_images/)
python3 parse_final.py sample_file.FSN -e

# Extract to custom directory
python3 parse_final.py *.FSN --extract-images --output-dir my_images/
```

## Output Format

### Console Output

The parser displays:
- File information:
  - File size and data size
  - Total number of records
  - Image availability status (0x2E = has images, 0x2D = no images)
- Per-record information:
  - Record number
  - Date/Time of validation
  - Currency type (e.g., CNY)
  - Denomination (¥1, ¥5, ¥10, ¥50, ¥100)
  - Version/Year edition
  - Authenticity status (0-3)
  - Serial number (10 characters)
  - Bitmap info (if extracted)
- Session summaries:
  - Bills counted per denomination
  - Total value per session
- Overall summary:
  - Total counting sessions
  - Grand total bills and value by currency

### Example Output

```
$ python3 parse_final.py sample.fsn -e -o output_images
================================================================================
File: sample.fsn
================================================================================
File size: 83,582 bytes
Data size: 83,232 bytes
Record size: 1632 bytes
Total records: 51
Has bitmap images: YES (0x2E)
================================================================================

Record #  1: 2026-03-01 16:51:36 | JPY |  1000¥ | N/A  | Auth:1 | SN: AA######B
  Machine SN: MACHINE123
  Bitmap: 9 chars, 32x32 pixels
Record #  2: 2026-03-01 16:51:36 | JPY |  1000¥ | N/A  | Auth:1 | SN: XY######C
  Machine SN: MACHINE123
  Bitmap: 9 chars, 32x32 pixels
...

Record # 58: 2026-03-01 17:05:00 | CNY |     0 | N/A  | Auth:0 | Err:[21845,21845,32773] | SN: __________
  Machine SN: M
  Bitmap: 10 chars, 32x32 pixels

================================================================================
SESSION #1 SUMMARY - Currency: JPY
================================================================================
   1000¥ ×   6 =     6000¥
   5000¥ ×   1 =     5000¥
  10000¥ ×   1 =    10000¥
  ------------------------------
  TOTAL:   8 bills =    21000¥
================================================================================

...

Record # 20: 2026-03-01 16:52:20 | CNY |     1¥ | 2019 | Auth:1 | SN: AA########
  Machine SN: M
  Bitmap: 10 chars, 32x32 pixels
Record # 21: 2026-03-01 16:52:20 | CNY |     5¥ | 2020 | Auth:1 | SN: BB########
  Machine SN: M
  Bitmap: 10 chars, 32x32 pixels
...

================================================================================
GRAND TOTAL:  51 bills
================================================================================
```

**Note:** Actual output includes Machine SN and error codes when applicable. Currency symbols are correctly mapped (¥ for CNY/JPY, $ for USD, € for EUR, £ for GBP, etc.).

### Extracted Image Files

When using `--extract-images`, bitmap images are saved as PBM (Portable Bitmap) files:
- **Directory structure**: `output_dir/YYYY-MM-DD_HH-MM-SS/`
  - Each FSN file gets its own timestamped subdirectory
- **Filename format**: `{count}_{timestamp}_{denomination}_{serialNumber}.pbm`
  - Example: `001_2026-03-01_13-59-12_100_XXXXXXXXXX.pbm`
- **Image format**: PBM (P1) - Plain text portable bitmap
  - Can be viewed/converted with ImageMagick, GIMP, or other image tools
  - Example conversion: `convert image.pbm image.png`

## Technical Details

### Specification Reference

This parser is based on the official specification: **"银行现金处理��备冠字号码查询管理数据格式"** (Bank Cash Processing Equipment Serial Number Query Management Data Format).

However, the actual FSN10 files use an **extended/modified version** of the specification:
- **Original spec**: ~32-byte header, 100-byte metadata per record
- **FSN10 format**: 350-byte extended header, 88-byte modified metadata per record
- **Format version**: HeadString[1] = 2 (vs. spec's value of 1)

### Reverse Engineering Process

This implementation was developed through:
1. **Specification analysis**: Starting from the official Chinese banking specification
2. **Pattern analysis**: Scanning for valid date/time patterns in binary data
3. **Record size discovery**: Calculating gaps between consecutive valid records (1632 bytes)
4. **Structure validation**: Verifying record alignment and data consistency
5. **Field identification**: Comparing extracted data with known bill properties
6. **Bitmap decoding**: Analyzing TImageSNo structures and pixel layouts per spec

### Key Differences from Original Spec

| Aspect | Original Spec | FSN10 Implementation |
|--------|--------------|---------------------|
| Header Size | ~32 bytes | 350 bytes (extended) |
| Format Version | HeadString[1] = 1 | HeadString[1] = 2 |
| Metadata Size | 100 bytes | 88 bytes |
| Record Size | Variable | 1632 bytes fixed |
| Serial Number | Uint16[12] (24 bytes) | Uint16[13] (26 bytes, UTF-16LE) |
| Machine Serial | Uint16[24] (48 bytes) | Field layout differs |
| RMB Editions | 0-2 (1990/1999/2005) | 0-5 (extended to 2015/2019/2020) |

### Data Structure
```python
{
    'record_num': int,          # Sequential record number
    'datetime': str,            # YYYY-MM-DD HH:MM:SS
    'currency': str,            # e.g., "CNY"
    'denomination': int,        # 1, 5, 10, 50, 100
    'version': str,             # e.g., "2019"
    'authenticity': int,        # 0-3
    'serial_number': str        # 10-character serial
}
```

## Requirements

- Python 3.6+
- No external dependencies (uses only Python standard library)

## Files

- **parse_final.py** - Main FSN10 parser with bitmap extraction
- **monitor_fsn.py** - FSN file monitoring utility
- **list.csv** - Bill inventory reference
- **README.md** - This file
- **FSN10_*.FSN** - Sample FSN10 files
- **extracted_images/** - Output directory for extracted bitmaps (created when using `-e`)

## License

See your organization's licensing terms.

## Features

- ✅ Parse FSN10 format files with 1632-byte records
- ✅ Extract bill metadata (serial numbers, denominations, timestamps)
- ✅ Support for multiple currencies (CNY, HKD, etc.)
- ✅ Automatic session detection based on time gaps
- ✅ Extract serial number bitmap images to PBM format
- ✅ Batch processing of multiple FSN files
- ✅ Detailed summaries per session and overall
- ✅ Version/edition mapping (1990-2020 editions)

## Bitmap Image Structure

The serial number bitmaps use the **TImageSNo** structure:

```c
struct TImgSNoData {
    Uint32 Data[32];  // 32 columns, each column is a 32-bit value
};

struct TImageSNo {
    Int16  Num;           // Number of characters (e.g., 10)
    Int16  height;        // Character height in pixels (e.g., 32)
    Int16  width;         // Character width in pixels (e.g., 24)
    Uint16 Reserve2;      // Reserved
    TImgSNoData SNo[12];  // Up to 12 character bitmaps
};
```

### Bitmap Encoding

- Each character is encoded as 32 uint32 values (one per column)
- Each uint32 represents one vertical column of pixels
- Bits are ordered MSB to LSB: bit 31 = row 0, bit 30 = row 1, ..., bit 0 = row 31
- Maximum dimensions: 32×32 pixels per character
- Typical dimensions: 32×24 (height × width)
