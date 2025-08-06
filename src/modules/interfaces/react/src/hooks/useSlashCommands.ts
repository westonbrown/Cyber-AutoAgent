/**
 * Slash Commands Hook
 * Implements slash commands for quick actions and navigation
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
          console.log('\n▣ Cyber-AutoAgent Command Reference\n');
          console.log('ASSESSMENT COMMANDS:');
          console.log('  target <url>          - Set assessment target');
          console.log('  execute [objective]   - Start assessment with optional focus');
          console.log('  reset                 - Clear current configuration\n');
          
          console.log('SLASH COMMANDS:');
          console.log('  /help                 - Show this help message');
          console.log('  /docs                 - Browse documentation interactively');
          console.log('  /plugins              - Select security assessment module');
          console.log('  /config               - View current configuration');
          console.log('  /config edit          - Edit configuration interactively');
          console.log('  /health               - Check system and container status');
          console.log('  /setup                - Choose deployment mode\n');
          
          console.log('CONFIGURATION:');
          console.log('  /provider <type>      - Switch AI provider (bedrock/ollama/litellm)');
          console.log('  /iterations <num>     - Set max tool executions (1-200)');
          console.log('  /region <aws-region>  - Set AWS region for Bedrock');
          console.log('  /observability <on/off> - Toggle Langfuse tracing');
          console.log('  /debug <on/off>       - Toggle verbose debug output\n');
          
          console.log('UTILITIES:');
          console.log('  /clear                - Clear terminal screen');
          console.log('  /exit                 - Exit application\n');
          
          console.log('KEYBOARD SHORTCUTS:');
          console.log('  Tab                   - Autocomplete suggestions');
          console.log('  ↑↓                    - Navigate suggestions');
          console.log('  Ctrl+C                - Clear input / Pause assessment');
          console.log('  Ctrl+L                - Clear screen');
          console.log('  Esc                   - Close modals (component-specific)\n');
          
          console.log('EXAMPLES:');
          console.log('  target https://testphp.vulnweb.com');
          console.log('  execute focus on OWASP Top 10\n');
          
          console.log('For detailed instructions, use: /docs');
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
        command: '/docs',
        description: 'Browse documentation interactively',
        action: async (args) => {
          // Parse document number if provided
          const docNumber = args.length > 0 ? parseInt(args[0]) : undefined;
          
          if (docNumber && (isNaN(docNumber) || docNumber < 1 || docNumber > 7)) {
            console.log('Invalid document number. Please use a number between 1 and 7.');
            return;
          }
          
          // Signal to open documentation viewer modal
          // This will be handled by the App component
          console.log('OPEN_DOCS_MODAL', docNumber);
        },
        args: ['document_number']
      },
      {
        command: '/plugins',
        description: 'Select security assessment module interactively',
        action: async (args) => {
          if (args.length === 0) {
            console.log('\n▣ Security Assessment Modules\n');
            console.log('Current module:', currentModule || 'general');
            console.log('\nAvailable modules:');
            Object.entries(availableModules).forEach(([name, module]) => {
              const isCurrent = name === currentModule;
              console.log(`  ${isCurrent ? '▶' : '•'} ${name} - ${module.description || 'Security assessment module'}`);
            });
            console.log('\nUse /plugins in the main interface to select interactively.');
            return;
          }
          
          // Direct module switching if name provided
          const moduleName = args[0];
          if (availableModules[moduleName]) {
            await switchModule(moduleName);
            console.log(`✓ Switched to module: ${moduleName}`);
          } else {
            console.log(`Unknown module: ${moduleName}`);
            console.log('Available modules:', Object.keys(availableModules).join(', '));
          }
        },
        args: ['module_name']
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
        }
      },
      {
        command: '/setup',
        description: 'Launch deployment setup wizard',
        action: () => {
          // This command will be handled by the app router to show InitializationFlow
          console.log('Opening setup wizard...');
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