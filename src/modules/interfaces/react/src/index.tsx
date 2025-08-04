#!/usr/bin/env node
import React from 'react';
import {render} from 'ink';
import meow from 'meow';
import {App} from './App.js';

const cli = meow(`
  Usage
    $ cyber-react [options]

  Options
    --target, -t         Target system/network to assess
    --objective, -o      Security assessment objective
    --module, -m         Security module to use (default: general)
    --iterations, -i     Maximum tool executions (default: 50)
    --auto-run          Start assessment immediately without UI
    --auto-approve      Auto-approve tool executions (no confirmations)
    --memory-mode       Memory mode: auto (default) or fresh
    --provider          Model provider: bedrock (default), ollama, or litellm
    --model             Specific model ID to use
    --region            AWS region (default: us-east-1)
    --observability     Enable observability tracing (default: true)
    --debug, -d         Enable debug mode
    --headless          Run in headless mode for scripting

  Examples
    $ cyber-react
    $ cyber-react --module general
    $ cyber-react --target example.com --objective "vulnerability scan" --auto-run
    $ cyber-react -t 192.168.1.100 -o "port scan and service enumeration" -i 25 --auto-approve
`, {
  importMeta: import.meta,
  flags: {
    target: {
      type: 'string',
      shortFlag: 't'
    },
    objective: {
      type: 'string',
      shortFlag: 'o'
    },
    module: {
      type: 'string',
      shortFlag: 'm',
      default: 'general'
    },
    iterations: {
      type: 'number',
      shortFlag: 'i',
      default: 50
    },
    autoRun: {
      type: 'boolean',
      default: false
    },
    autoApprove: {
      type: 'boolean',
      default: false
    },
    memoryMode: {
      type: 'string',
      default: 'auto'
    },
    provider: {
      type: 'string',
      default: 'bedrock'
    },
    model: {
      type: 'string'
    },
    region: {
      type: 'string',
      default: 'us-east-1'
    },
    observability: {
      type: 'boolean',
      default: true
    },
    debug: {
      type: 'boolean',
      shortFlag: 'd'
    },
    headless: {
      type: 'boolean',
      default: false
    }
  }
});

// Check if we're running in a TTY environment
const isRawModeSupported = process.stdin.isTTY;

if (!isRawModeSupported && !cli.flags.headless) {
  console.log('⚠️  Running in non-interactive mode. Use --headless flag for scripting.');
  console.log('💡 For interactive mode, run directly in a terminal.');
  
  // Provide basic CLI functionality
  if (cli.flags.target && cli.flags.autoRun) {
    console.log(`🔐 Starting assessment: ${cli.flags.module} → ${cli.flags.target}`);
    console.log(`📌 Objective: ${cli.flags.objective || 'General security assessment'}`);
    // In production, this would execute the assessment
    process.exit(0);
  } else {
    console.log('\nUsage: cyber-react --target <target> --auto-run');
    process.exit(1);
  }
}

// Render the app with CLI arguments
const app = render(<App 
  module={cli.flags.module}
  target={cli.flags.target}
  objective={cli.flags.objective}
/>);

// Handle graceful shutdown
process.on('SIGINT', () => {
  app.unmount();
  process.exit(0);
});