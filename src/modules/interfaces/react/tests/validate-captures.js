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
    
    // 6. Use frame analyzer for comprehensive check
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