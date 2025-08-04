/**
 * Slash Commands Hook
 * Implements Gemini CLI-style slash commands for quick actions
 */

import { useCallback } from 'react';
import { useModule } from '../contexts/ModuleContext.js';
import { useConfig } from '../contexts/ConfigContext.js';
import { HealthMonitor } from '../services/HealthMonitor.js';

interface SlashCommand {
  command: string;
  description: string;
  action: (args: string[]) => Promise<void> | void;
  args?: string[];
}

export const useSlashCommands = () => {
  const { switchModule, availableModules, currentModule } = useModule();
  const { config, updateConfig } = useConfig();

  const getSlashCommands = useCallback((): SlashCommand[] => {
    return [
      {
        command: '/help',
        description: 'Show available commands and shortcuts',
        action: () => {
          console.log('Cyber-AutoAgent Slash Commands:');
          console.log('/scan <target> - Quick vulnerability scan');
          console.log('/module <name> - Switch security module');
          console.log('/target <ip/url> - Set assessment target');
          console.log('/config - Show current configuration');
          console.log('/health - Check container health status');
          console.log('/history - Show command history');
          console.log('/clear - Clear screen');
          console.log('/exit - Exit application');
        }
      },
      {
        command: '/health',
        description: 'Check container health status',
        action: async () => {
          const monitor = HealthMonitor.getInstance();
          const { status, recommendations } = await monitor.getDetailedHealth();
          
          console.log('\nContainer Health Status\n' + '─'.repeat(40));
          console.log(`Overall Status: ${status.overall.toUpperCase()}`);
          console.log(`Docker Running: ${status.dockerRunning ? 'Yes' : 'No'}`);
          console.log(`\nServices:`);
          
          status.services.forEach(svc => {
            const statusSymbol = 
              svc.status === 'running' ? '✓' : 
              svc.status === 'stopped' ? '✗' : 
              '⚠';
            const healthInfo = svc.health ? ` (${svc.health})` : '';
            const uptimeInfo = svc.uptime ? ` - ${svc.uptime}` : '';
            
            console.log(`  ${statusSymbol} ${svc.displayName}: ${svc.status}${healthInfo}${uptimeInfo}`);
            if (svc.url) {
              console.log(`    URL: ${svc.url}`);
            }
            if (svc.message) {
              console.log(`    Note: ${svc.message}`);
            }
          });
          
          if (recommendations.length > 0) {
            console.log(`\nRecommendations:`);
            recommendations.forEach(rec => {
              console.log(`  • ${rec}`);
            });
          }
          
          console.log(`\nLast checked: ${status.lastCheck.toLocaleTimeString()}`);
        }
      },
      {
        command: '/scan',
        description: 'Quick vulnerability scan of target',
        action: (args) => {
          if (args.length === 0) {
            console.log('Usage: /scan <target>');
            return;
          }
          const target = args[0];
          // This would trigger a quick scan
          console.log(`Starting quick scan of ${target}...`);
        },
        args: ['target']
      },
      {
        command: '/module',
        description: 'Switch to different security module',
        action: async (args) => {
          if (args.length === 0) {
            console.log('Available modules:', Object.keys(availableModules).join(', '));
            console.log('Current module:', currentModule);
            return;
          }
          
          const moduleName = args[0];
          if (availableModules[moduleName]) {
            await switchModule(moduleName);
            console.log(`Switched to module: ${moduleName}`);
          } else {
            console.log(`Unknown module: ${moduleName}`);
            console.log('Available modules:', Object.keys(availableModules).join(', '));
          }
        },
        args: ['module_name']
      },
      {
        command: '/target',
        description: 'Set assessment target',
        action: (args) => {
          if (args.length === 0) {
            console.log('Usage: /target <ip_or_url>');
            return;
          }
          const target = args[0];
          console.log(`Target set to: ${target}`);
          // This would update the current target
        },
        args: ['ip_or_url']
      },
      {
        command: '/config',
        description: 'Show current configuration',
        action: () => {
          console.log('Current Configuration:');
          console.log(`Model Provider: ${config.modelProvider}`);
          console.log(`Model ID: ${config.modelId}`);
          console.log(`AWS Region: ${config.awsRegion}`);
          console.log(`Docker Image: ${config.dockerImage}`);
          console.log(`Iterations: ${config.iterations}`);
          console.log(`Auto Approve: ${config.autoApprove}`);
          console.log(`Memory Mode: ${config.memoryMode}`);
        }
      },
      {
        command: '/provider',
        description: 'Switch model provider',
        action: async (args) => {
          if (args.length === 0) {
            console.log('Usage: /provider <bedrock|ollama|litellm>');
            console.log('Current provider:', config.modelProvider);
            return;
          }
          
          const provider = args[0];
          const validProviders = ['bedrock', 'ollama', 'litellm'];
          
          if (validProviders.includes(provider)) {
            await updateConfig({ modelProvider: provider as 'bedrock' | 'ollama' | 'litellm' });
            console.log(`Provider switched to: ${provider}`);
          } else {
            console.log(`Invalid provider. Valid options: ${validProviders.join(', ')}`);
          }
        },
        args: ['provider']
      },
      {
        command: '/iterations',
        description: 'Set maximum iterations for assessment',
        action: async (args) => {
          if (args.length === 0) {
            console.log('Usage: /iterations <number>');
            console.log('Current iterations:', config.iterations);
            return;
          }
          
          const iterations = parseInt(args[0]);
          if (isNaN(iterations) || iterations < 1 || iterations > 1000) {
            console.log('Iterations must be a number between 1 and 1000');
            return;
          }
          
          await updateConfig({ iterations });
          console.log(`Iterations set to: ${iterations}`);
        },
        args: ['number']
      },
      {
        command: '/memory',
        description: 'Configure memory settings',
        action: async (args) => {
          if (args.length === 0) {
            console.log('Usage: /memory <auto|fresh>');
            console.log('Current memory mode:', config.memoryMode);
            return;
          }
          
          const mode = args[0] as 'auto' | 'fresh';
          if (['auto', 'fresh'].includes(mode)) {
            await updateConfig({ memoryMode: mode });
            console.log(`Memory mode set to: ${mode}`);
          } else {
            console.log('Memory mode must be "auto" or "fresh"');
          }
        },
        args: ['mode']
      },
      {
        command: '/region',
        description: 'Set AWS region for Bedrock',
        action: async (args) => {
          if (args.length === 0) {
            console.log('Usage: /region <aws_region>');
            console.log('Current region:', config.awsRegion);
            return;
          }
          
          const region = args[0];
          await updateConfig({ awsRegion: region });
          console.log(`AWS region set to: ${region}`);
        },
        args: ['aws_region']
      },
      {
        command: '/history',
        description: 'Show command history',
        action: () => {
          console.log('Command history feature coming soon...');
        }
      },
      {
        command: '/clear',
        description: 'Clear the screen',
        action: () => {
          console.clear();
        }
      },
      {
        command: '/exit',
        description: 'Exit the application',
        action: () => {
          process.exit(0);
        }
      },
      {
        command: '/debug',
        description: 'Toggle debug mode',
        action: async (args) => {
          const enable = args.length === 0 ? !config.verbose : args[0] === 'on';
          await updateConfig({ verbose: enable });
          console.log(`Debug mode ${enable ? 'enabled' : 'disabled'}`);
        },
        args: ['on|off']
      },
      {
        command: '/observability',
        description: 'Toggle observability tracing',
        action: async (args) => {
          const enable = args.length === 0 ? !config.enableObservability : args[0] === 'on';
          await updateConfig({ enableObservability: enable });
          console.log(`Observability ${enable ? 'enabled' : 'disabled'}`);
        },
        args: ['on|off']
      }
    ];
  }, [availableModules, currentModule, switchModule, config, updateConfig]);

  const executeSlashCommand = useCallback(async (commandLine: string) => {
    const parts = commandLine.trim().split(/\s+/);
    const commandName = parts[0];
    const args = parts.slice(1);

    const commands = getSlashCommands();
    const command = commands.find(cmd => cmd.command === commandName);

    if (command) {
      try {
        await command.action(args);
      } catch (error) {
        console.error(`Error executing ${commandName}:`, error.message);
      }
    } else {
      console.log(`Unknown command: ${commandName}`);
      console.log('Type /help for available commands');
    }
  }, [getSlashCommands]);

  const getCommandSuggestions = useCallback((partial: string): SlashCommand[] => {
    const commands = getSlashCommands();
    return commands.filter(cmd => 
      cmd.command.toLowerCase().startsWith(partial.toLowerCase())
    );
  }, [getSlashCommands]);

  return {
    getSlashCommands,
    executeSlashCommand,
    getCommandSuggestions
  };
};