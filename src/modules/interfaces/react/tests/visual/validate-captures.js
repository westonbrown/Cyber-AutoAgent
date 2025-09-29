#!/usr/bin/env node

/**
 * Terminal Capture Validation Helper
 * 
 * Analyzes captured terminal output for common UI issues
 * and prepares data for Claude validation
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { FrameAnalyzer } from './frame-analyzer.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const capturesDir = join(__dirname, 'captures');

class CaptureValidator {
  constructor() {
    this.analyzer = new FrameAnalyzer(80, 24);
    this.issues = [];
  }

  validateCapture(filepath, content) {
    const issues = [];
    
    // Extract actual terminal content (skip metadata)
    const lines = content.split('\n');
    const separatorIndex = lines.findIndex(line => line.match(/^=+$/));
    const terminalContent = lines.slice(separatorIndex + 1).join('\n');
    
    // 1. Check for double branding
    const brandingMatches = terminalContent.match(/╔═╗╦ ╦╔╗ ╔═╗╦═╗/g) || [];
    if (brandingMatches.length > 1) {
      issues.push({
        type: 'DOUBLE_BRANDING',
        severity: 'HIGH',
        description: `Found ${brandingMatches.length} instances of ASCII branding`,
        line: terminalContent.split('\n').findIndex(line => line.includes('╔═╗╦ ╦╔╗ ╔═╗╦═╗'))
      });
    }
    
    // 2. Check for duplicate logs
    const logPattern = /\[\d{1,2}:\d{2}:\d{2} [AP]M\] .+/g;
    const logs = terminalContent.match(logPattern) || [];
    const logCounts = new Map();
    logs.forEach(log => {
      const cleanLog = log.replace(/\[\d{1,2}:\d{2}:\d{2} [AP]M\]/, '[TIME]');
      logCounts.set(cleanLog, (logCounts.get(cleanLog) || 0) + 1);
    });
    
    logCounts.forEach((count, log) => {
      if (count > 2) {
        issues.push({
          type: 'DUPLICATE_LOGS',
          severity: 'MEDIUM',
          description: `Log entry appears ${count} times: "${log}"`,
          count: count
        });
      }
    });
    
    // 3. Check for overlapping UI elements
    const hasSetupElements = terminalContent.includes('Environment Configuration') || 
                             terminalContent.includes('Setup Progress');
    const hasMainElements = terminalContent.includes('Type target <url>') || 
                           terminalContent.includes('general: target');
    
    if (hasSetupElements && hasMainElements) {
      issues.push({
        type: 'UI_OVERLAP',
        severity: 'HIGH',
        description: 'Setup UI elements overlapping with main interface'
      });
    }
    
    // 4. Check for visible escape sequences
    if (terminalContent.includes('^[')) {
      issues.push({
        type: 'VISIBLE_ESCAPES',
        severity: 'MEDIUM',
        description: 'Escape sequences visible as text (^[)'
      });
    }
    
    // 5. Check for error text
    const errorPatterns = [
      { pattern: /undefined/g, desc: 'undefined values' },
      { pattern: /null(?!able)/g, desc: 'null values' },
      { pattern: /\[object Object\]/g, desc: 'unrendered objects' },
      { pattern: /NaN/g, desc: 'NaN values' },
      { pattern: /require is not defined/g, desc: 'require errors' }
    ];
    
    errorPatterns.forEach(({ pattern, desc }) => {
      const matches = terminalContent.match(pattern);
      if (matches) {
        issues.push({
          type: 'ERROR_TEXT',
          severity: 'HIGH',
          description: `Found ${desc}: ${matches.length} occurrences`
        });
      }
    });
    
    // 6. Validate tool display format (TEST-VALIDATION-SPECIFICATION.md requirement)
    const toolDisplayIssues = this.validateToolDisplayFormat(terminalContent);
    issues.push(...toolDisplayIssues);
    
    // 7. Validate step header format
    const stepHeaderIssues = this.validateStepHeaderFormat(terminalContent);
    issues.push(...stepHeaderIssues);
    
    // 8. Validate output display format
    const outputDisplayIssues = this.validateOutputDisplayFormat(terminalContent);
    issues.push(...outputDisplayIssues);
    
    // 9. Validate ThinkingIndicator animation (no static text)
    const animationIssues = this.validateAnimationBehavior(terminalContent);
    issues.push(...animationIssues);
    
    // 10. Validate footer information format
    const footerIssues = this.validateFooterFormat(terminalContent);
    issues.push(...footerIssues);
    
    // 11. Validate modal system behavior
    const modalIssues = this.validateModalSystem(terminalContent);
    issues.push(...modalIssues);
    
    // 12. Use frame analyzer for comprehensive check
    const analysis = this.analyzer.analyzeFrame(terminalContent);
    if (!analysis.valid) {
      analysis.issues.forEach(issue => {
        issues.push({
          type: 'FRAME_ANALYSIS',
          severity: 'MEDIUM',
          description: issue
        });
      });
    }
    
    return issues;
  }

  /**
   * Validate tool display format according to TEST-VALIDATION-SPECIFICATION.md
   * Required format:
   * tool: {tool_name}
   * ├─ param1: value1
   * ├─ param2: value2
   * └─ param3: value3
   *   ⠋ Executing [animation]
   */
  validateToolDisplayFormat(content) {
    const issues = [];
    
    // Find tool executions
    const toolLines = content.split('\n').filter(line => line.trim().startsWith('tool:'));
    
    toolLines.forEach((toolLine, index) => {
      const lines = content.split('\n');
      const toolLineIndex = lines.indexOf(toolLine);
      
      // Check tool name format
      if (!toolLine.match(/tool:\s+\w+/)) {
        issues.push({
          type: 'TOOL_FORMAT_ERROR',
          severity: 'HIGH',
          description: `Tool line doesn't match required format "tool: {name}": "${toolLine.trim()}"`,
          line: toolLineIndex
        });
      }
      
      // Check for tree-style parameters on following lines
      let nextLineIndex = toolLineIndex + 1;
      let foundParameters = false;
      let foundEndMarker = false;
      
      while (nextLineIndex < lines.length && !foundEndMarker) {
        const nextLine = lines[nextLineIndex].trim();
        
        // Check for parameter lines with tree characters
        if (nextLine.match(/^[├└]─\s+\w+:/)) {
          foundParameters = true;
          if (nextLine.startsWith('└─')) {
            foundEndMarker = true;
          }
        } else if (nextLine.includes('⠋') || nextLine.includes('Executing')) {
          // Found animation/execution line - stop checking
          break;
        } else if (nextLine === '') {
          // Empty line - continue
        } else {
          // Non-parameter line found - stop checking
          break;
        }
        
        nextLineIndex++;
      }
      
      // Validate parameter format if parameters were found
      if (foundParameters && !foundEndMarker) {
        issues.push({
          type: 'TOOL_PARAMS_FORMAT',
          severity: 'MEDIUM',
          description: `Tool parameters missing proper tree ending (└─) for tool: ${toolLine.trim()}`,
          line: toolLineIndex
        });
      }
    });
    
    // Check for old format violations
    const oldFormatLines = content.split('\n').filter(line => 
      line.includes('Commands:') || line.includes('[tool]') || line.includes('executing')
    );
    
    if (oldFormatLines.length > 0) {
      issues.push({
        type: 'OLD_TOOL_FORMAT',
        severity: 'HIGH',
        description: `Found deprecated tool format. Should use "tool: name" format. Found: ${oldFormatLines.length} instances`
      });
    }
    
    return issues;
  }

  /**
   * Validate step header format
   * Required format: [STEP X/Y] • [AGENT_INFO] ─────────────────
   */
  validateStepHeaderFormat(content) {
    const issues = [];
    
    const stepLines = content.split('\n').filter(line => 
      line.includes('STEP') && (line.includes('/') || line.includes('FINAL'))
    );
    
    stepLines.forEach(line => {
      const trimmed = line.trim();
      
      // Check for proper step format
      if (!trimmed.match(/\[(?:STEP \d+\/\d+|FINAL STEP \d+\/\d+|FINAL REPORT)\]/)) {
        issues.push({
          type: 'STEP_HEADER_FORMAT',
          severity: 'HIGH',
          description: `Step header doesn't match required format: "${trimmed}"`
        });
      }
      
      // Check for divider line presence
      if (!trimmed.includes('─')) {
        issues.push({
          type: 'STEP_DIVIDER_MISSING',
          severity: 'MEDIUM',
          description: `Step header missing divider line: "${trimmed}"`
        });
      }
    });
    
    return issues;
  }

  /**
   * Validate output display format
   * Required format: output (exit: 0, duration: 2.5s)
   */
  validateOutputDisplayFormat(content) {
    const issues = [];
    
    const outputLines = content.split('\n').filter(line => 
      line.includes('output') && (line.includes('exit:') || line.includes('duration:'))
    );
    
    outputLines.forEach(line => {
      const trimmed = line.trim();
      
      // Check for proper output header format
      if (!trimmed.match(/output\s*\(exit:\s*\d+,\s*duration:\s*[\d.]+s\)/)) {
        issues.push({
          type: 'OUTPUT_HEADER_FORMAT',
          severity: 'MEDIUM',
          description: `Output header doesn't match required format: "${trimmed}"`
        });
      }
    });
    
    return issues;
  }

  /**
   * Validate ThinkingIndicator animation behavior
   * Should NOT show static "⠋ Executing" text
   */
  validateAnimationBehavior(content) {
    const issues = [];
    
    // Check for static animation text (bad)
    if (content.includes('⠋ Executing') && !content.includes('⠙') && !content.includes('⠹')) {
      issues.push({
        type: 'STATIC_ANIMATION',
        severity: 'HIGH',
        description: 'Found static "⠋ Executing" text instead of animated spinner'
      });
    }
    
    // Check for inline animation with tool name (bad)
    const lines = content.split('\n');
    const inlineAnimationLines = lines.filter(line => 
      line.includes('tool:') && line.includes('⠋')
    );
    
    if (inlineAnimationLines.length > 0) {
      issues.push({
        type: 'INLINE_ANIMATION',
        severity: 'HIGH',
        description: `Found animation inline with tool name (should be separate): ${inlineAnimationLines.length} instances`
      });
    }
    
    return issues;
  }

  /**
   * Validate footer information format
   * Required format: [Status] | 1,500 tokens • $0.05 • 2m 30s • [ESC] Kill Switch | ● provider | model-id
   */
  validateFooterFormat(content) {
    const issues = [];
    
    // Look for footer-like content
    const footerLines = content.split('\n').filter(line => 
      line.includes('tokens') || line.includes('Kill Switch') || line.includes('ESC')
    );
    
    footerLines.forEach(line => {
      const trimmed = line.trim();
      
      // Check for token formatting with commas
      const tokenMatch = trimmed.match(/(\d+)\s+tokens/);
      if (tokenMatch && parseInt(tokenMatch[1]) >= 1000 && !tokenMatch[1].includes(',')) {
        issues.push({
          type: 'TOKEN_FORMAT',
          severity: 'LOW',
          description: `Token count should use comma formatting: "${tokenMatch[1]}" should be formatted with commas`
        });
      }
      
      // Check for ESC key instruction
      if (trimmed.includes('Kill Switch') && !trimmed.includes('[ESC]')) {
        issues.push({
          type: 'ESC_INSTRUCTION_FORMAT',
          severity: 'MEDIUM',
          description: 'Kill Switch should include [ESC] key instruction'
        });
      }
    });
    
    return issues;
  }

  /**
   * Validate modal system behavior
   */
  validateModalSystem(content) {
    const issues = [];
    
    // Check for modal overlap issues
    const hasConfigModal = content.includes('Configuration') && content.includes('section');
    const hasSafetyModal = content.includes('Safety Warning') || content.includes('authorization');
    const hasMainInterface = content.includes('Type target') || content.includes('general:');
    
    if ((hasConfigModal || hasSafetyModal) && hasMainInterface) {
      // This might be normal during transitions, so lower severity
      issues.push({
        type: 'POTENTIAL_MODAL_OVERLAP',
        severity: 'LOW',
        description: 'Modal and main interface elements both visible (check if this is during transition)'
      });
    }
    
    // Check for modal keyboard navigation hints
    if (hasConfigModal && !content.includes('Tab') && !content.includes('Arrow')) {
      issues.push({
        type: 'MODAL_NAVIGATION_MISSING',
        severity: 'MEDIUM',
        description: 'Configuration modal missing keyboard navigation hints (Tab, Arrow keys)'
      });
    }
    
    return issues;
  }

  validateJourney(journeyDir) {
    const journeyName = path.basename(journeyDir);
    console.log(`\n🔍 Validating: ${journeyName}`);
    console.log('─'.repeat(60));
    
    const journeyIssues = [];
    const captures = fs.readdirSync(journeyDir)
      .filter(f => f.endsWith('.txt') && !f.includes('SUMMARY'))
      .sort();
    
    captures.forEach(filename => {
      const filepath = join(journeyDir, filename);
      const content = fs.readFileSync(filepath, 'utf8');
      const issues = this.validateCapture(filepath, content);
      
      if (issues.length > 0) {
        console.log(`  ❌ ${filename}: ${issues.length} issues found`);
        journeyIssues.push({ filename, issues });
      } else {
        console.log(`  ✅ ${filename}: Clean`);
      }
    });
    
    return { journey: journeyName, issues: journeyIssues };
  }

  generateReport(validationResults) {
    const reportPath = join(capturesDir, 'VALIDATION-REPORT.md');
    
    const totalIssues = validationResults.reduce((sum, r) => 
      sum + r.issues.reduce((s, i) => s + i.issues.length, 0), 0
    );
    
    const report = [
      '# Terminal Capture Validation Report',
      '',
      `**Generated:** ${new Date().toISOString()}`,
      `**Total Issues Found:** ${totalIssues}`,
      '',
      '## Summary by Journey',
      '',
      ...validationResults.map(r => {
        const journeyIssueCount = r.issues.reduce((s, i) => s + i.issues.length, 0);
        return `- **${r.journey}**: ${journeyIssueCount} issues`;
      }),
      '',
      '## Detailed Issues',
      ''
    ];
    
    validationResults.forEach(result => {
      if (result.issues.length > 0) {
        report.push(`### ${result.journey}`);
        report.push('');
        
        result.issues.forEach(({ filename, issues }) => {
          report.push(`#### ${filename}`);
          report.push('');
          issues.forEach(issue => {
            const icon = issue.severity === 'HIGH' ? '🔴' : '🟡';
            report.push(`- ${icon} **${issue.type}**: ${issue.description}`);
          });
          report.push('');
        });
      }
    });
    
    // Add issue type statistics
    const issueTypes = new Map();
    validationResults.forEach(r => {
      r.issues.forEach(({ issues }) => {
        issues.forEach(issue => {
          issueTypes.set(issue.type, (issueTypes.get(issue.type) || 0) + 1);
        });
      });
    });
    
    report.push('## Issue Type Distribution');
    report.push('');
    Array.from(issueTypes.entries())
      .sort((a, b) => b[1] - a[1])
      .forEach(([type, count]) => {
        report.push(`- **${type}**: ${count} occurrences`);
      });
    
    fs.writeFileSync(reportPath, report.join('\n'));
    return reportPath;
  }
}

// Main validation
async function main() {
  console.log('🔍 Terminal Capture Validation');
  console.log('==============================');
  
  if (!fs.existsSync(capturesDir)) {
    console.error('❌ No captures found. Run terminal-capture.js first.');
    process.exit(1);
  }
  
  const validator = new CaptureValidator();
  const validationResults = [];
  
  // Get all journey directories
  const journeyDirs = fs.readdirSync(capturesDir)
    .filter(f => fs.statSync(join(capturesDir, f)).isDirectory())
    .map(f => join(capturesDir, f));
  
  // Validate each journey
  journeyDirs.forEach(journeyDir => {
    const result = validator.validateJourney(journeyDir);
    validationResults.push(result);
  });
  
  // Generate report
  const reportPath = validator.generateReport(validationResults);
  
  console.log('\n📊 Validation Complete');
  console.log(`📄 Report: ${reportPath}`);
  
  // Show summary
  const totalIssues = validationResults.reduce((sum, r) => 
    sum + r.issues.reduce((s, i) => s + i.issues.length, 0), 0
  );
  
  if (totalIssues === 0) {
    console.log('\n✅ All captures passed validation!');
  } else {
    console.log(`\n⚠️  Found ${totalIssues} total issues across all journeys`);
    console.log('Please review the captures manually for visual quality');
  }
}

main().catch(error => {
  console.error('❌ Validation error:', error);
  process.exit(1);
});