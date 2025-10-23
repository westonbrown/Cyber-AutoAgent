# Knowledge Base

Preloaded, offline domain knowledge for security assessments. This KB provides curated reference knowledge about CVEs, threat actors, TTPs, and exploit patterns.

## Structure

```
data/kb/
├── README.md               # This file
├── manifest.json          # Version and metadata
├── build_kb.py            # Index generation script
├── content/               # JSONL knowledge entries
│   ├── cves.jsonl        # CVE patterns and exploitation notes
│   ├── techniques.jsonl  # MITRE ATT&CK techniques
│   ├── payloads.jsonl    # Exploit payload templates
│   └── actors.jsonl      # Threat actor profiles
└── index/                # FAISS vector index
    └── embeddings.faiss  # Prebuilt search index
```

## Usage

The KB is automatically loaded when enabled and provides a `retrieve_kb` tool for the agent:

```python
# Query KB for exploitation techniques
retrieve_kb("blind XSS detection techniques")

# Filter by domain
retrieve_kb("SSTI payloads", filters={"domain": "web"})

# Filter by category and tags
retrieve_kb("APT28 TTPs", filters={"tactic": "credential_access"})
```

## Configuration

**Enable/Disable:**
```bash
export CYBER_KB_ENABLED=true
```

**Max Results:**
```bash
export CYBER_KB_MAX_RESULTS=3
```

**CLI Flags:**
```bash
python src/cyberautoagent.py --kb-enabled --kb-max-results 5 ...
```

## Adding New Entries

1. **Edit JSONL files** in `content/` directory

Entry format:
```json
{
  "id": "unique-identifier",
  "domain": "web|network|api|cloud",
  "category": "cve|technique|payload|actor",
  "content": "Concise description (200-400 tokens)",
  "tags": ["tag1", "tag2", "tag3"],
  "source": "Reference source"
}
```

2. **Regenerate index:**
```bash
python data/kb/build_kb.py
```

3. **Commit changes:**
```bash
git add data/kb/
git commit -m "Update KB: Added new CVE entries"
```

## Current Content

### CVEs (5 entries)
- CVE-2021-44228 (Log4Shell)
- CVE-2022-30190 (Follina)
- CVE-2023-22515 (Confluence)
- CVE-2023-34362 (MOVEit)
- CVE-2024-3094 (XZ Backdoor)

### Techniques (8 entries)
- Blind XSS detection
- SSTI detection and exploitation
- Time-based blind SQL injection
- JWT algorithm confusion
- SSRF to cloud metadata
- XXE file read
- IDOR detection
- NoSQL injection (MongoDB)

### Payloads (5 entries)
- XSS basic payloads
- Jinja2 SSTI RCE
- SQL injection UNION
- LFI to RCE
- XXE out-of-band

### Threat Actors (4 entries)
- APT28 (Fancy Bear)
- APT29 (Cozy Bear)
- Lazarus Group
- Cl0p Ransomware Group

## KB vs Operation Memory

| Feature | Knowledge Base | Operation Memory |
|---------|---------------|------------------|
| **Purpose** | Static reference knowledge | Dynamic evidence collection |
| **Scope** | Cross-target | Per-target |
| **Mutability** | Read-only | Read-write |
| **Updates** | Via releases | During operations |
| **Storage** | `data/kb/` | `outputs/<target>/memory/` |
| **Tool** | `retrieve_kb` | `mem0_memory` |

## Maintenance

### Version Updates

Update `manifest.json` after major changes:

```json
{
  "version": "v0.2.0",
  "created_at": "2025-10-22T02:38:00Z",
  "entry_count": 25,
  "has_faiss_index": true
}
```

### Index Regeneration

The FAISS index should be regenerated when:
- Adding new entries
- Updating existing content
- Changing embedding model

```bash
python data/kb/build_kb.py
```

Note: Currently uses text search fallback. FAISS semantic search will be enabled when embedding generation is implemented in the build script.

## License

KB content is curated from public sources (OWASP, MITRE ATT&CK, CVE database) and licensed under MIT. See LICENSE file in repository root.

## References

- OWASP Top 10: https://owasp.org/www-project-top-ten/
- MITRE ATT&CK: https://attack.mitre.org/
- CVE Database: https://cve.mitre.org/
- PayloadsAllTheThings: https://github.com/swisskyrepo/PayloadsAllTheThings
