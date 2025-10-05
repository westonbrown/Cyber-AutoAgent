# Threat Emulation Report Template

Generate a comprehensive adversary emulation report documenting TTPs executed, detection opportunities created, and blue team recommendations.

## Report Structure

### Executive Summary
- APT group/campaign emulated
- Kill chain phases executed
- TTPs successfully demonstrated
- Key detection opportunities
- Blue team readiness assessment

### Campaign Overview
**Emulated Threat Actor**: [APT group/campaign name]
**Target Environment**: [network/AD/cloud description]
**Emulation Duration**: [start - end time]
**Kill Chain Coverage**: [phases executed]

### TTP Execution Timeline

For each TTP executed, document:
- **[Phase]** T####.### - [Technique Name]
  - **Objective**: What this TTP achieves
  - **Execution**: How it was simulated
  - **Marker Created**: [file/registry/network/process indicator]
  - **Detection Opportunity**: [Event ID/log source/behavioral signature]
  - **Blue Team Action**: What defenders should monitor

### Indicators of Compromise (IoCs)

Categorized by type:
- **Files**: [paths and hashes of marker files]
- **Registry**: [keys created during emulation]
- **Network**: [domains/IPs contacted]
- **Processes**: [marker process names and command lines]
- **Users**: [test accounts created]

### Attack Chain Visualization

```
[Initial Access] → [Persistence] → [Privilege Escalation] → [Lateral Movement] → [Objectives]
     TTP              TTP              TTP                      TTP                TTP
```

### Detection Recommendations

**High Priority** (Critical detection gaps):
- [Techniques with no current detection]
- Recommended monitoring configurations
- Alert rules to implement

**Medium Priority** (Partial visibility):
- [Techniques with incomplete coverage]
- Enhancement opportunities

**Low Priority** (Adequate detection):
- [Techniques currently detected]
- Validation of existing controls

### Blue Team Training Opportunities

Based on this emulation:
1. [Detection engineering focus areas]
2. [Incident response scenarios to practice]
3. [Security control gaps to address]

### Cleanup Verification

- [x] All marker files removed
- [x] Test accounts deleted
- [x] Scheduled tasks/services removed
- [x] Registry keys cleaned
- [x] No residual artifacts

### Operational Notes

**What Worked**:
- [TTPs that executed successfully]
- [Environment characteristics that enabled TTPs]

**What Was Blocked**:
- [TTPs prevented by defenses]
- [Security controls that performed well]

**Recommendations**:
- [Defensive improvements based on findings]
- [Detection engineering priorities]
- [Incident response preparation]

---

**Report Classification**: INTERNAL - Blue Team Training Material
**Emulation Ethics**: All activities were marker-based simulations. No actual harm, data theft, or system compromise occurred.
