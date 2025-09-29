/**
 * Terminal Frame Analyzer
 *
 * Comprehensive analysis of captured terminal frames to detect
 * UI issues, rendering artifacts, and ensure production quality
 */
export class FrameAnalyzer {
    constructor(terminalWidth = 80, terminalHeight = 24) {
        this.terminalWidth = terminalWidth;
        this.terminalHeight = terminalHeight;
    }
    /**
     * Comprehensive frame analysis
     */
    analyzeFrame(frame) {
        const issues = [];
        const metrics = this.calculateMetrics(frame);
        const artifacts = this.detectArtifacts(frame);
        // 1. Check for rendering completeness
        if (metrics.totalLines < 5) {
            issues.push('Frame appears incomplete (too few lines)');
        }
        if (metrics.blankLines > metrics.totalLines * 0.7) {
            issues.push('Frame is mostly blank (>70% empty lines)');
        }
        // 2. Check for text overflow
        if (metrics.overflowLines > 0) {
            issues.push(`${metrics.overflowLines} lines exceed terminal width`);
        }
        // 3. Check for duplicate headers
        if (metrics.headerCount > 1) {
            issues.push(`Multiple headers detected (${metrics.headerCount})`);
        }
        // 4. Check for ANSI corruption
        if (artifacts.incompleteAnsi.length > 0) {
            issues.push(`Incomplete ANSI sequences: ${artifacts.incompleteAnsi.join(', ')}`);
        }
        // 5. Check for screen clearing artifacts
        if (artifacts.clearScreenSequences.length > 0) {
            issues.push('Clear screen sequences detected in output');
        }
        // 6. Check for overlapping UI elements
        if (artifacts.overlappingElements.length > 0) {
            issues.push(`Overlapping UI elements: ${artifacts.overlappingElements.join(', ')}`);
        }
        // 7. Check for corrupted text
        if (artifacts.corruptedText.length > 0) {
            issues.push(`Corrupted text detected: ${artifacts.corruptedText.join(', ')}`);
        }
        // 8. Check for excessive duplicate content
        if (metrics.duplicateLines > metrics.totalLines * 0.3) {
            issues.push('Excessive duplicate lines (>30%)');
        }
        return {
            valid: issues.length === 0,
            issues,
            metrics,
            artifacts
        };
    }
    /**
     * Calculate frame metrics
     */
    calculateMetrics(frame) {
        const lines = frame.split('\n');
        const cleanLines = lines.map(line => this.stripAnsi(line));
        // Count duplicate lines
        const lineOccurrences = new Map();
        cleanLines.forEach(line => {
            lineOccurrences.set(line, (lineOccurrences.get(line) || 0) + 1);
        });
        const duplicateLines = Array.from(lineOccurrences.values())
            .filter(count => count > 1)
            .reduce((sum, count) => sum + count - 1, 0);
        // Count headers (various patterns)
        const headerPatterns = [
            /CYBER.*AUTOAGENT/gi,
            /╔═╗╦ ╦╔╗ ╔═╗╦═╗/g,
            /Full Spectrum Cyber Operations/g
        ];
        const headerCount = headerPatterns.reduce((count, pattern) => count + (frame.match(pattern) || []).length, 0);
        // Count ANSI sequences
        const ansiPattern = /\x1b\[[0-9;]*[mGKHJlh]/g;
        const ansiSequences = (frame.match(ansiPattern) || []).length;
        // Find overflow lines
        const overflowLines = cleanLines.filter(line => line.length > this.terminalWidth).length;
        return {
            totalLines: lines.length,
            blankLines: cleanLines.filter(line => line.trim() === '').length,
            contentLines: cleanLines.filter(line => line.trim() !== '').length,
            maxLineLength: Math.max(...cleanLines.map(line => line.length)),
            ansiSequences,
            duplicateLines,
            headerCount,
            overflowLines
        };
    }
    /**
     * Detect various rendering artifacts
     */
    detectArtifacts(frame) {
        const artifacts = {
            clearScreenSequences: [],
            cursorMovements: [],
            incompleteAnsi: [],
            controlCharacters: [],
            duplicateContent: [],
            overlappingElements: [],
            corruptedText: []
        };
        // 1. Clear screen sequences
        const clearPatterns = [
            /\x1b\[2J/g, // Clear entire screen
            /\x1b\[H/g, // Cursor home
            /\x1b\[3J/g, // Clear scrollback
            /\x1bc/g // Reset terminal
        ];
        clearPatterns.forEach(pattern => {
            const matches = frame.match(pattern);
            if (matches) {
                artifacts.clearScreenSequences.push(...matches);
            }
        });
        // 2. Cursor movements (should be minimal in captured output)
        const cursorPatterns = [
            /\x1b\[\d+A/g, // Cursor up
            /\x1b\[\d+B/g, // Cursor down
            /\x1b\[\d+C/g, // Cursor forward
            /\x1b\[\d+D/g, // Cursor back
            /\x1b\[\d+;\d+H/g // Cursor position
        ];
        cursorPatterns.forEach(pattern => {
            const matches = frame.match(pattern);
            if (matches && matches.length > 5) { // More than 5 cursor movements is suspicious
                artifacts.cursorMovements.push(...matches);
            }
        });
        // 3. Incomplete ANSI sequences
        const incompleteAnsi = frame.match(/\x1b\[[^m]*$/g) || [];
        artifacts.incompleteAnsi.push(...incompleteAnsi);
        // 4. Control characters (except newline and ANSI)
        const controlChars = frame.match(/[\x00-\x08\x0B-\x0C\x0E-\x1A\x1C-\x1F]/g) || [];
        artifacts.controlCharacters.push(...controlChars.map(char => `\\x${char.charCodeAt(0).toString(16).padStart(2, '0')}`));
        // 5. Detect overlapping UI elements
        const uiPatterns = [
            { name: 'setup', pattern: /Setup Wizard|Environment Configuration/g },
            { name: 'main', pattern: /Type target <url>|general: target/g },
            { name: 'config', pattern: /Configuration Editor|AWS Configuration/g },
            { name: 'memory', pattern: /Memory Search|Search memories/g },
            { name: 'help', pattern: /Available Commands|Slash Commands/g }
        ];
        const detectedUIs = [];
        uiPatterns.forEach(({ name, pattern }) => {
            if (pattern.test(frame)) {
                detectedUIs.push(name);
            }
        });
        // Check for incompatible UI combinations
        if (detectedUIs.includes('setup') && detectedUIs.includes('main')) {
            artifacts.overlappingElements.push('Setup wizard overlapping with main UI');
        }
        if (detectedUIs.length > 1 && !detectedUIs.includes('main')) {
            artifacts.overlappingElements.push(`Multiple modals active: ${detectedUIs.join(', ')}`);
        }
        // 6. Detect corrupted text patterns
        const corruptionPatterns = [
            /undefined/g,
            /null/g,
            /\[object Object\]/g,
            /NaN/g,
            /TypeError:|ReferenceError:/g,
            /\{\{.*\}\}/g, // Unrendered template variables
        ];
        corruptionPatterns.forEach(pattern => {
            const matches = frame.match(pattern);
            if (matches) {
                artifacts.corruptedText.push(...matches);
            }
        });
        // 7. Detect duplicate log entries
        const logPattern = /\[\d{1,2}:\d{2}:\d{2} [AP]M\] .+/g;
        const logs = frame.match(logPattern) || [];
        const logCounts = new Map();
        logs.forEach(log => {
            const cleanLog = log.replace(/\[\d{1,2}:\d{2}:\d{2} [AP]M\]/, '[TIME]');
            logCounts.set(cleanLog, (logCounts.get(cleanLog) || 0) + 1);
        });
        logCounts.forEach((count, log) => {
            if (count > 2) {
                artifacts.duplicateContent.push(`Log repeated ${count} times: ${log}`);
            }
        });
        return artifacts;
    }
    /**
     * Compare two frames for flicker detection
     */
    compareFrames(frame1, frame2) {
        const lines1 = frame1.split('\n');
        const lines2 = frame2.split('\n');
        const differences = [];
        let hasFlicker = false;
        // Check for significant structural changes
        if (Math.abs(lines1.length - lines2.length) > 10) {
            hasFlicker = true;
            differences.push(`Line count changed drastically: ${lines1.length} -> ${lines2.length}`);
        }
        // Check for header position changes
        const header1Index = lines1.findIndex(line => /CYBER.*AUTOAGENT/.test(line));
        const header2Index = lines2.findIndex(line => /CYBER.*AUTOAGENT/.test(line));
        if (header1Index !== -1 && header2Index !== -1 && header1Index !== header2Index) {
            hasFlicker = true;
            differences.push(`Header moved from line ${header1Index} to ${header2Index}`);
        }
        // Check for complete content replacement
        const content1 = this.stripAnsi(frame1);
        const content2 = this.stripAnsi(frame2);
        const similarity = this.calculateSimilarity(content1, content2);
        if (similarity < 0.3) {
            hasFlicker = true;
            differences.push(`Content changed dramatically (${Math.round(similarity * 100)}% similar)`);
        }
        return { hasFlicker, differences };
    }
    /**
     * Validate frame sequence for smooth transitions
     */
    validateFrameSequence(frames) {
        const issues = [];
        for (let i = 1; i < frames.length; i++) {
            const analysis1 = this.analyzeFrame(frames[i - 1]);
            const analysis2 = this.analyzeFrame(frames[i]);
            // Check each frame is valid
            if (!analysis1.valid) {
                issues.push(`Frame ${i - 1}: ${analysis1.issues.join(', ')}`);
            }
            if (!analysis2.valid) {
                issues.push(`Frame ${i}: ${analysis2.issues.join(', ')}`);
            }
            // Check for flicker between frames
            const { hasFlicker, differences } = this.compareFrames(frames[i - 1], frames[i]);
            if (hasFlicker) {
                issues.push(`Flicker detected between frames ${i - 1} and ${i}: ${differences.join(', ')}`);
            }
        }
        return {
            valid: issues.length === 0,
            issues
        };
    }
    /**
     * Strip ANSI codes from text
     */
    stripAnsi(text) {
        return text.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '');
    }
    /**
     * Calculate text similarity (0-1)
     */
    calculateSimilarity(text1, text2) {
        if (text1 === text2)
            return 1;
        if (!text1 || !text2)
            return 0;
        const longer = text1.length > text2.length ? text1 : text2;
        const shorter = text1.length > text2.length ? text2 : text1;
        const editDistance = this.levenshteinDistance(shorter, longer);
        return (longer.length - editDistance) / longer.length;
    }
    /**
     * Calculate Levenshtein distance
     */
    levenshteinDistance(str1, str2) {
        const matrix = [];
        for (let i = 0; i <= str2.length; i++) {
            matrix[i] = [i];
        }
        for (let j = 0; j <= str1.length; j++) {
            matrix[0][j] = j;
        }
        for (let i = 1; i <= str2.length; i++) {
            for (let j = 1; j <= str1.length; j++) {
                if (str2.charAt(i - 1) === str1.charAt(j - 1)) {
                    matrix[i][j] = matrix[i - 1][j - 1];
                }
                else {
                    matrix[i][j] = Math.min(matrix[i - 1][j - 1] + 1, matrix[i][j - 1] + 1, matrix[i - 1][j] + 1);
                }
            }
        }
        return matrix[str2.length][str1.length];
    }
}
