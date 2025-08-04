#!/usr/bin/env node
import { spawn } from 'child_process';

console.log('🚀 Starting Cyber-AutoAgent validation test...\n');

const child = spawn('npm', ['start'], {
  stdio: ['pipe', 'pipe', 'pipe'],
  env: { ...process.env, FORCE_COLOR: '1', NODE_ENV: 'development' }
});

let fullOutput = '';
let reasoningBuffer = '';
let toolsFound = [];

// Process output
child.stdout.on('data', (data) => {
  const text = data.toString();
  fullOutput += text;
  process.stdout.write(text);
  
  // Check for tool displays
  if (text.includes('tool:')) {
    const toolMatch = text.match(/tool:\s*(\w+)/);
    if (toolMatch) {
      toolsFound.push(toolMatch[1]);
    }
  }
  
  // Check for reasoning
  if (text.includes('reasoning')) {
    reasoningBuffer += text;
  }
});

child.stderr.on('data', (data) => {
  process.stderr.write(data);
});

// Send test commands
async function runTest() {
  await delay(3000);
  
  console.log('\n📝 Configuring provider...');
  child.stdin.write('/config\n');
  await delay(500);
  child.stdin.write('provider\n');
  await delay(500);
  child.stdin.write('bedrock\n');
  await delay(500);
  child.stdin.write('done\n');
  
  await delay(1000);
  console.log('\n📦 Loading web_security module...');
  child.stdin.write('module web_security\n');
  
  await delay(1000);
  console.log('\n🎯 Setting target...');
  child.stdin.write('target https://example.com\n');
  
  await delay(1000);
  console.log('\n🚀 Executing assessment (30 second test)...');
  child.stdin.write('execute\n');
  
  // Let it run
  await delay(30000);
  
  console.log('\n🛑 Stopping assessment...');
  child.stdin.write('/stop\n');
  
  await delay(2000);
  child.stdin.write('/exit\n');
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Run the test
runTest().catch(console.error);

// Check results on exit
child.on('exit', (code) => {
  console.log('\n\n📊 VALIDATION RESULTS:');
  console.log('====================');
  
  // Check for reasoning display
  const hasReasoning = fullOutput.includes('reasoning');
  const reasoningSplit = reasoningBuffer.includes('Initi\n') || reasoningBuffer.includes('ating\n');
  console.log(`✓ Reasoning displayed: ${hasReasoning ? '✅ PASS' : '❌ FAIL'}`);
  console.log(`✓ Reasoning not split: ${!reasoningSplit ? '✅ PASS' : '❌ FAIL'}`);
  
  // Check for tools
  console.log(`✓ Tools found: ${toolsFound.length > 0 ? '✅ PASS' : '❌ FAIL'}`);
  if (toolsFound.length > 0) {
    console.log(`  - Tools displayed: ${toolsFound.join(', ')}`);
  }
  
  // Check for shell commands
  const hasCommands = fullOutput.includes('⎿');
  console.log(`✓ Commands displayed: ${hasCommands ? '✅ PASS' : '❌ FAIL'}`);
  
  // Check for output
  const hasOutput = fullOutput.includes('output');
  console.log(`✓ Output displayed: ${hasOutput ? '✅ PASS' : '❌ FAIL'}`);
  
  // Performance check (look for timing in output)
  const timingMatch = fullOutput.match(/(\d+)m\s*(\d+)s/);
  if (timingMatch) {
    const minutes = parseInt(timingMatch[1]);
    const seconds = parseInt(timingMatch[2]);
    const totalSeconds = minutes * 60 + seconds;
    console.log(`✓ Performance: ${totalSeconds}s ${totalSeconds < 60 ? '✅ FAST' : totalSeconds < 120 ? '⚠️  OK' : '❌ SLOW'}`);
  }
  
  console.log('\nTest completed.');
  process.exit(0);
});