/**
 * Deployment Recovery Component
 * 
 * Manages recovery actions and remediation procedures for unhealthy deployments.
 * Shows inline recovery options without requiring full setup wizard.
 */

import React, { useState, useCallback } from 'react';
import { Box, Text, useInput } from 'ink';
import Spinner from 'ink-spinner';
import { useConfig } from '../contexts/ConfigContext.js';
import { DeploymentStatus } from '../services/DeploymentDetector.js';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

interface DeploymentRecoveryProps {
  deployment: DeploymentStatus;
  onComplete: (success: boolean) => void;
  onSkip: () => void;
}

export const DeploymentRecovery: React.FC<DeploymentRecoveryProps> = ({
  deployment,
  onComplete,
  onSkip
}) => {
  const [isRecovering, setIsRecovering] = useState(false);
  const [recoveryMessage, setRecoveryMessage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const { updateConfig, saveConfig } = useConfig();

  // Handle recovery based on deployment mode and issues
  const handleRecovery = useCallback(async () => {
    setIsRecovering(true);
    setError(null);
    
    try {
      switch (deployment.mode) {
        case 'local-cli':
          await recoverPythonEnvironment();
          break;
        case 'single-container':
          await recoverDockerContainer();
          break;
        case 'full-stack':
          await recoverFullStack();
          break;
      }
      
      // Update configuration to mark as configured
      await updateConfig({
        deploymentMode: deployment.mode,
        isConfigured: true,
        hasSeenWelcome: true
      });
      await saveConfig();
      
      setRecoveryMessage('✅ Recovery complete!');
      setTimeout(() => onComplete(true), 1500);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Recovery failed');
      setIsRecovering(false);
    }
  }, [deployment, updateConfig, saveConfig, onComplete]);

  // Recovery functions for each deployment type
  const recoverPythonEnvironment = async () => {
    setRecoveryMessage('Setting up Python environment...');
    
    // Check what's missing
    if (!deployment.details.venvExists) {
      setRecoveryMessage('Creating virtual environment...');
      await execAsync('python3 -m venv .venv');
    }
    
    setRecoveryMessage('Installing dependencies...');
    const venvPip = '.venv/bin/pip';
    await execAsync(`${venvPip} install --upgrade pip`);
    await execAsync(`${venvPip} install -e .`);
    
    setRecoveryMessage('Verifying installation...');
    await execAsync('.venv/bin/python -c "import cyberautoagent"');
  };

  const recoverDockerContainer = async () => {
    setRecoveryMessage('Recovering Docker container...');
    
    // Check if container exists but is stopped
    try {
      const { stdout } = await execAsync('docker ps -a --filter name=cyber-autoagent --format "{{.Status}}"');
      if (stdout.includes('Exited')) {
        setRecoveryMessage('Starting stopped container...');
        await execAsync('docker start cyber-autoagent');
      } else if (!stdout) {
        setRecoveryMessage('Creating new container...');
        await execAsync('docker run -d --name cyber-autoagent cyber-autoagent:latest');
      }
    } catch (err) {
      throw new Error('Failed to recover Docker container');
    }
    
    setRecoveryMessage('Waiting for container to be healthy...');
    await new Promise(resolve => setTimeout(resolve, 3000));
  };

  const recoverFullStack = async () => {
    setRecoveryMessage('Recovering full stack deployment...');
    
    // Try to start all containers with docker-compose
    try {
      setRecoveryMessage('Starting Docker Compose stack...');
      await execAsync('docker-compose up -d', { cwd: process.cwd() });
      
      setRecoveryMessage('Waiting for services to initialize...');
      await new Promise(resolve => setTimeout(resolve, 5000));
      
      // Check Langfuse health
      setRecoveryMessage('Verifying Langfuse connection...');
      const maxRetries = 10;
      for (let i = 0; i < maxRetries; i++) {
        try {
          const response = await fetch('http://localhost:3000/api/public/health');
          if (response.ok) break;
        } catch {
          if (i === maxRetries - 1) {
            throw new Error('Langfuse service not responding after recovery');
          }
          await new Promise(resolve => setTimeout(resolve, 2000));
        }
      }
    } catch (err) {
      throw new Error('Failed to recover full stack deployment');
    }
  };

  // Keyboard input handling
  useInput((input, key) => {
    if (!isRecovering) {
      if (key.return || input === 'y' || input === 'Y') {
        handleRecovery();
      } else if (key.escape || input === 'n' || input === 'N' || input === 's' || input === 'S') {
        onSkip();
      }
    }
  });

  // Render recovery UI
  return (
    <Box flexDirection="column" paddingX={2} paddingY={1}>
      <Box marginBottom={1}>
        <Text bold color="yellow">
          ⚠️  Deployment Recovery Needed
        </Text>
      </Box>

      <Box flexDirection="column" marginBottom={1}>
        <Text>
          Mode: <Text color="cyan">{deployment.mode}</Text>
        </Text>
        <Text color="red">
          • Deployment is not running or unhealthy
        </Text>
        <Text color="green">
          💡 Try running setup again or switch to a different deployment mode
        </Text>
      </Box>

      {isRecovering ? (
        <Box>
          <Text color="cyan">
            <Spinner type="dots" /> {recoveryMessage}
          </Text>
        </Box>
      ) : error ? (
        <Box flexDirection="column">
          <Text color="red">❌ {error}</Text>
          <Text color="dim">Press [Y] to retry, [S] to skip</Text>
        </Box>
      ) : (
        <Box flexDirection="column">
          <Text>
            Would you like to automatically fix these issues?
          </Text>
          <Text color="dim">
            Press [Y] to fix, [S] to skip
          </Text>
        </Box>
      )}
    </Box>
  );
};