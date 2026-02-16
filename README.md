# 🔍 mlocate Toolkit

**Python tools for working with mlocate — build databases and parse original mlocate.db binary files**

> Works on **Windows**, **Linux**, and **macOS** — zero external dependencies

---

## 📦 Contents

| File | Description |
|------|-------------|
| `mylocate.py` | Build SQLite database & fast file search (mlocate alternative) |
| `mlocate_reader.py` | Parse & search original Linux `mlocate.db` binary files |
| `CHEATSHEET.md` | Comprehensive mlocate cheat sheet |

---

## 🚀 Quick Start

### mylocate.py — Build Your Own Database

```bash
# Index entire filesystem
sudo python3 mylocate.py updatedb

# Index specific directory
python3 mylocate.py updatedb --root /home

# Windows
python mylocate.py updatedb --root C:\Users

# Search
python3 mylocate.py search "config"
python3 mylocate.py search "*.log" -i
python3 mylocate.py search "^test.*\.py$" -r

# Stats
python3 mylocate.py stats
```

### mlocate_reader.py — Read Original mlocate.db Files

```bash
# Copy the database from a Linux server
scp user@server:/var/lib/mlocate/mlocate.db .

# Search
python3 mlocate_reader.py mlocate.db -s "passwd"
python3 mlocate_reader.py mlocate.db -s "*.conf" -g
python3 mlocate_reader.py mlocate.db -s "ssh" -i -l 20

# Save results to file
python3 mlocate_reader.py mlocate.db -s "home" -o results.txt

# Stats
python3 mlocate_reader.py mlocate.db --stats
```

---

## 🔧 mylocate.py — Reference

### Commands

| Command | Description |
|---------|-------------|
| `updatedb` | Build / update the database |
| `search` | Search for files |
| `stats` | Show database statistics |

### updatedb Options

| Option | Description | Default |
|--------|-------------|---------|
| `--db PATH` | Database path | `~/.mylocate.db` |
| `--root PATH` | Root directory to index | `/` |

### search Options

| Option | Description |
|--------|-------------|
| `-i, --ignore-case` | Case-insensitive search |
| `-l N, --limit N` | Max number of results |
| `-r, --regex` | Use regular expressions |
| `-b, --basename` | Search filename only |
| `--db PATH` | Database path |

---

## 📖 mlocate_reader.py — Reference

| Option | Description |
|--------|-------------|
| `-s, --search PATTERN` | Search pattern |
| `-i, --ignore-case` | Case-insensitive search |
| `-g, --glob` | Glob pattern search (e.g. `*.txt`) |
| `-r, --regex` | Regular expression search |
| `-l N, --limit N` | Max number of results |
| `-c, --count` | Show result count only |
| `-o FILE, --output FILE` | Save results to file |
| `--stats` | Show database statistics |

---

## 🛡️ Security Note

The `mlocate.db` file contains a full filesystem index including all file names and paths for every user. If you obtain a copy of this file from a server, you can see:

- Other users' file paths and filenames
- Sensitive filenames (e.g. `creds-for-2022.txt`)
- Installed application structures (e.g. LimeSurvey, Apache, etc.)
- System information and installed packages

**Useful for:**
- Penetration Testing
- Digital Forensics
- Security Auditing

---

## 📋 Requirements

- Python 3.6+
- No external libraries (Standard Library only)

---

## 📄 License

MIT License
