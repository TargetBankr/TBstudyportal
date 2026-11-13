"""
HARTRON DEO question bank - topic map.

Each mock = (id, title, focus, count). Count is 25..50. Each subject totals 750.
`focus` is what the model is told to cover (taken from the syllabus map).
Edit counts here if you want a different split; run `python generate.py --check`
afterwards to confirm totals.
"""

SUBJECTS = {
    1: {
        "name": "Windows, Networking and Computer Fundamentals",
        "slug": "subject1",
        "target": 750,
        "mocks": [
            # 1.1 Introduction to Computer (50)
            ("S1_01", "Introduction to Computer",
             "definition and characteristics of a computer (speed, accuracy, diligence, storage, versatility); "
             "generations of computers; types by size and purpose (super, mainframe, mini, micro, laptop, tablet); "
             "analog, digital, hybrid; block diagram and input-process-output-storage; famous names (Charles Babbage, ENIAC, UNIVAC, Von Neumann)", 50),
            # 1.2 Hardware (75)
            ("S1_02", "Hardware - Input and Output Devices",
             "input devices (keyboard, mouse, scanner, light pen, OMR, OCR, MICR, barcode reader, touch screen, webcam, microphone, joystick); "
             "output devices (monitor CRT/LCD/LED, dot matrix/inkjet/laser printers, plotter, speaker, projector)", 40),
            ("S1_03", "Hardware - CPU, Memory, Storage, Units and Ports",
             "CPU (ALU, control unit, registers), clock speed, cores; memory (register, cache, RAM SRAM/DRAM, ROM PROM/EPROM/EEPROM, flash); "
             "storage (HDD, SSD, CD, DVD, Blu-ray, pen drive, memory card, cloud); units of memory (bit, nibble, byte, KB, MB, GB, TB, PB); "
             "ports and connectors (USB, HDMI, VGA, serial, parallel, PS/2, LAN port); motherboard, SMPS, chipset, expansion slots, BIOS/CMOS", 35),
            # 1.3 Inside the PC (30)
            ("S1_04", "Inside the PC",
             "motherboard parts, RAM slots, CPU socket, PCI/PCIe, SATA; cabinet, SMPS, cooling fan, heat sink; "
             "booting (cold/warm boot, POST), BIOS/UEFI; device drivers, plug and play", 30),
            # 1.4 Software (65)
            ("S1_05", "Software - System and Application Software",
             "system software (OS, utility, language translators, device drivers); application software (general purpose, specific purpose, packages); "
             "compiler, interpreter, assembler; machine, assembly and high level languages; open source vs proprietary, freeware, shareware, firmware", 35),
            ("S1_06", "Software - Operating System and Malware Basics",
             "operating system functions; types of OS (batch, multitasking, multiuser, real time, GUI/CUI); "
             "virus, worm, trojan, malware, antivirus, firewall basics", 30),
            # 1.5 Number System (70)
            ("S1_07", "Number System - Conversions and Arithmetic",
             "binary, octal, decimal, hexadecimal; conversions between all bases (include small calculation questions); "
             "binary addition and subtraction, 1s and 2s complement", 40),
            ("S1_08", "Number System - Codes and Logic Gates",
             "ASCII, Unicode, BCD, EBCDIC; logic gates (AND, OR, NOT, NAND, NOR, XOR) basics and truth tables", 30),
            # 1.6 Windows basics, Drives and File Management (100)
            ("S1_09", "Windows - Desktop, Drives and Partitions",
             "desktop, taskbar, Start menu, icons, shortcuts, wallpaper, screen saver; drives (C:, D:, removable, network drive), partition, formatting, FAT32/NTFS", 30),
            ("S1_10", "Windows - Files, Folders, Extensions and Recycle Bin",
             "create, copy, move, rename, delete, properties, hidden and read-only; file extensions (.txt .doc .docx .xls .xlsx .ppt .pptx .pdf .jpg .png .mp3 .mp4 .exe .html); "
             "Recycle Bin, Shift+Delete, restore", 35),
            ("S1_11", "Windows - Control Panel, Task Manager, Shortcuts and Accessories",
             "Control Panel, Settings, Add/Remove programs, Task Manager, Device Manager; keyboard shortcuts (Win+L, Win+D, Win+E, Win+R, Alt+Tab, Alt+F4, Ctrl+Shift+Esc, F2, F5); "
             "lock, sleep, hibernate, shut down, restart, log off; File Explorer basics; accessories (Notepad, WordPad, Paint, Calculator, Snipping tool)", 35),
            # 1.7 Multimedia (25)
            ("S1_12", "Concept of Multimedia",
             "components (text, graphics, audio, video, animation); file formats (MP3/WAV, MP4/AVI/MKV, JPEG/PNG/GIF/BMP); "
             "sound card, graphics card, speakers, webcam; applications of multimedia", 25),
            # 1.8 Computer Room (25)
            ("S1_13", "Setting and Protection of Computer Room and Computer",
             "ideal room conditions (temperature, humidity, dust, ventilation, lighting); UPS, stabilizer, surge protector, earthing; "
             "fire safety, anti-static precautions; ergonomics; data backup, password protection, antivirus, updates; physical vs software security", 25),
            # 1.9 Email / Internet / Extranet / WWW (50)
            ("S1_14", "Internet, Intranet, Extranet and WWW",
             "internet vs intranet vs extranet; WWW, web page, website, home page, URL, hyperlink; search engines, browser, downloading and uploading", 25),
            ("S1_15", "E-mail and E-services",
             "email terms (To, Cc, Bcc, subject, attachment, inbox, spam, drafts, forward, reply, reply all); email address format, popular mail services; "
             "social media, e-commerce, e-banking, e-governance basics", 25),
            # 1.10 Basic Networking Concepts (75)
            ("S1_16", "Networking - Types, Topologies, Media and Modes",
             "PAN, LAN, MAN, WAN; bus, star, ring, mesh, tree, hybrid topologies; transmission media (twisted pair, coaxial, optical fibre, microwave, satellite, Wi-Fi, Bluetooth); "
             "simplex, half duplex, full duplex", 40),
            ("S1_17", "Networking - Models, Client-Server and Bandwidth",
             "OSI model (7 layers) and TCP/IP model (4 layers); client-server vs peer-to-peer; bandwidth, bps, latency", 35),
            # 1.11 Networking Devices (35)
            ("S1_18", "Networking Devices",
             "NIC, hub, switch, bridge, repeater, router, gateway, modem, access point; difference between hub, switch and router; RJ45, crimping, straight and cross cable", 35),
            # 1.12 Network Basics and Configuration (75)
            ("S1_19", "Network Configuration - IP, DNS, DHCP, MAC and Commands",
             "IPv4 (32-bit) and IPv6 (128-bit), classes A to E, private vs public IP; subnet mask, default gateway, DNS, DHCP, MAC address; ping, ipconfig, tracert", 40),
            ("S1_20", "Network Protocols, Ports and Domain Names",
             "HTTP, HTTPS, FTP, SMTP, POP3, IMAP, TCP, UDP, Telnet, SSH and their purpose/ports; domain name basics (.com .org .gov .in .edu .net)", 35),
            # 1.13 Servers and Network Security (50)
            ("S1_21", "Servers",
             "server types (file, web, mail, database, proxy, print); role of servers in a network; client-server examples", 25),
            ("S1_22", "Network Security",
             "authentication, authorization, encryption, digital signature; firewall, proxy, VPN, antivirus; hacking, phishing, spoofing, ransomware, cyber crime basics; safe browsing and password hygiene", 25),
            # 1.14 IT Policy (25)
            ("S1_23", "IT Policy - Digital India, E-governance and IT Act",
             "Digital India programme, e-governance basics, IT Act 2000 basics, Haryana IT and e-governance initiatives, role of HARTRON, "
             "India-level IT policy basics. Keep facts well established and widely known; avoid obscure dates or figures that could be wrong", 25),
        ],
    },
    2: {
        "name": "Internet, HTML/DHTML and MS Office",
        "slug": "subject2",
        "target": 750,
        "mocks": [
            # 2.1 Browsers (70)
            ("S2_01", "Browsers - Settings, History, Cache and Cookies",
             "browser names (Chrome, Firefox, Edge, Safari, Opera); bookmarks, history, cache, cookies, incognito/private mode, downloads; "
             "tabs, home page, default search engine, pop-up blocker, extensions", 35),
            ("S2_02", "Browsers - Shortcuts and Security",
             "keyboard shortcuts (Ctrl+T, Ctrl+W, Ctrl+Shift+T, Ctrl+D, Ctrl+H, Ctrl+J, F5, Ctrl+L); security settings, certificates, HTTPS padlock; Firefox options and settings", 35),
            # 2.2 HTML (150)
            ("S2_03", "HTML - Structure, Headings, Formatting and Lists",
             "html, head, title, body; h1 to h6, p, br, hr; b, i, u, strong, em, sub, sup, mark; ul, ol, li, dl", 40),
            ("S2_04", "HTML - Links, Images and Tables",
             "a, href, target; img, src, alt, width, height; table, tr, td, th, colspan, rowspan, border", 40),
            ("S2_05", "HTML - Forms, Attributes and Entities",
             "form, input types, textarea, select, button, label; attributes, comments, entities; iframe, frames, div, span", 35),
            ("S2_06", "HTML - Mixed Concepts and File Basics",
             "file extensions .html and .htm, HTML versions, what HTML stands for, tags vs elements vs attributes, block vs inline, "
             "which tag does what (mixed recall across all HTML topics)", 35),
            # 2.3 DHTML (70)
            ("S2_07", "DHTML - Meaning and CSS",
             "meaning of DHTML (HTML + CSS + JavaScript + DOM); CSS inline, internal, external; selectors, colour, font, margin, padding", 35),
            ("S2_08", "DHTML - JavaScript, DOM and Static vs Dynamic Pages",
             "JavaScript basics (alert, variables, events like onclick, onmouseover); DOM; difference between static and dynamic pages", 35),
            # 2.4 MS Word (150)
            ("S2_09", "MS Word - Interface, Files, Editing and Formatting",
             "title bar, ribbon, tabs, quick access toolbar, status bar, ruler; new, open, save, save as, print, close, .docx and .doc; "
             "font, size, bold, italic, underline, colour, alignment, line spacing, bullets, numbering, indents", 40),
            ("S2_10", "MS Word - Insert Tab and Page Layout",
             "table, picture, shapes, header, footer, page number, symbol, text box, WordArt, hyperlink; margins, orientation, size, columns, breaks, watermark", 40),
            ("S2_11", "MS Word - Review, Mailings, View and Find/Replace",
             "spelling and grammar, thesaurus, word count, track changes, comments; mail merge, labels, envelopes; print layout, web layout, zoom, split window; "
             "Find and Replace, Format Painter, Undo and Redo", 35),
            ("S2_12", "MS Word - Shortcuts and Mixed Concepts",
             "Ctrl+B/I/U, Ctrl+C/X/V, Ctrl+Z/Y, Ctrl+A, Ctrl+S, Ctrl+P, Ctrl+F, Ctrl+H, Ctrl+E/L/R/J, Ctrl+Enter, F7; mixed recall across all Word topics", 35),
            # 2.5 MS Excel (160)
            ("S2_13", "MS Excel - Basics, Data Entry and Limits",
             "workbook, worksheet, cell, row, column, range, active cell, name box, formula bar; maximum rows (1048576) and columns (16384, up to XFD); "
             "data entry, auto fill, number formats (currency, date, percentage), alignment", 40),
            ("S2_14", "MS Excel - Formulas, References and Functions",
             "formulas and operators; relative, absolute and mixed references; SUM, AVERAGE, MAX, MIN, COUNT, COUNTA, IF, ROUND, LEN, UPPER, LOWER, CONCATENATE, "
             "TODAY, NOW, VLOOKUP, HLOOKUP, SUMIF, COUNTIF (include questions that ask for the output of a formula)", 50),
            ("S2_15", "MS Excel - Data Tools and Charts",
             "sort and filter, conditional formatting, data validation, freeze panes; column, bar, line, pie charts; pivot table basics", 35),
            ("S2_16", "MS Excel - Errors, Shortcuts and Page Setup",
             "page setup, print area, header and footer; error values (#DIV/0!, #NAME?, #VALUE!, #REF!, ####); "
             "shortcuts (Ctrl+N, Ctrl+O, Shift+F11, F2, F4, Ctrl+Arrow, Alt+=, Ctrl+;)", 35),
            # 2.6 PowerPoint (70)
            ("S2_17", "MS PowerPoint - Slides, Views, Themes and Insert",
             "slide, layout, design theme, template, slide master; normal, slide sorter, notes page, reading, slide show views; "
             "insert text box, picture, table, chart, SmartArt, video, audio, shapes", 35),
            ("S2_18", "MS PowerPoint - Animations, Shortcuts and File Types",
             "transitions vs animations, effects, timing; slide show shortcuts (F5, Shift+F5, Esc, N/P, B/W); handouts, notes; extensions .pptx and .ppt", 35),
            # 2.7 Windows Explorer (30)
            ("S2_19", "Windows Explorer",
             "File Explorer layout (address bar, navigation pane, views), copy, move, rename, search, properties, send to, compress and extract", 30),
            # 2.8 Email and Other Office Basics (50)
            ("S2_20", "MS Outlook and Email Software",
             "MS Outlook basics (inbox, calendar, contacts, tasks, signature, rules), email composing, attachments, folders, spam/junk", 25),
            ("S2_21", "MS Access and MS Paint",
             "MS Access basics (database, table, record, field, query, form, report, primary key, .accdb); MS Paint tools, file formats and basic operations", 25),
        ],
    },
}


def mocks_for(subject_no):
    return SUBJECTS[subject_no]["mocks"]


def validate_config():
    """Raise AssertionError if the topic map is inconsistent."""
    seen = set()
    for no, s in SUBJECTS.items():
        total = 0
        for mid, title, focus, count in s["mocks"]:
            assert mid not in seen, f"duplicate mock id {mid}"
            seen.add(mid)
            assert mid.startswith(f"S{no}_"), f"{mid} not in subject {no}"
            assert 25 <= count <= 50, f"{mid} count {count} outside 25..50"
            total += count
        assert total == s["target"], f"subject {no} totals {total}, expected {s['target']}"
    return True
