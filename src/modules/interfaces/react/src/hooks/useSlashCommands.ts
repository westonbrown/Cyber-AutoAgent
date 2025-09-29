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
          // This function should not be called directly - help should be handled by the useCommandHandler
          throw new Error('Help command should be handled by useCommandHandler');
        }
      },
      {
        command: '/health',
        description: 'Check container health status',
        action: async () => {
          // Health command should be handled by useCommandHandler
          throw new Error('Health command should be handled by useCommandHandler');
        }
      },
      {
        command: '/docs',
        description: 'Browse documentation interactively',
        action: async (args) => {
          // Parse document number if provided
          const docNumber = args.length > 0 ? parseInt(args[0]) : undefined;
          
          if (docNumber && (isNaN(docNumber) || docNumber < 1 || docNumber > 7)) {
            throw new Error('Invalid document number. Please use a number between 1 and 7.');
          }
          
          // Documentation should be handled by useCommandHandler
          throw new Error('Documentation command should be handled by useCommandHandler');
        },
        args: ['document_number']
      },
      {
        command: '/plugins',
        description: 'Select security assessment module interactively',
        action: async (args) => {
          // Plugins command should be handled by useCommandHandler
          throw new Error('Plugins command should be handled by useCommandHandler');
        },
        args: ['module_name']
      },
      {
        command: '/config',
        description: 'Show current configuration',
        action: () => {
          // Config command should be handled by useCommandHandler
          throw new Error('Config command should be handled by useCommandHandler');
        }
      },
      {
        command: '/setup',
        description: 'Launch deployment setup wizard',
        action: () => {
          // Setup command should be handled by useCommandHandler
          throw new Error('Setup command should be handled by useCommandHandler');
        }
      },
      {
        command: '/region',
        description: 'Set AWS region for Bedrock',
        action: async (args) => {
          // Region command should be handled by useCommandHandler or config UI
          throw new Error('Region command should be handled by useCommandHandler');
        },
        args: ['aws_region']
      },
      {
        command: '/clear',
        description: 'Clear the screen',
        action: () => {
          // Clear command should be handled by useCommandHandler
          throw new Error('Clear command should be handled by useCommandHandler');
        }
      },
      {
        command: '/exit',
        description: 'Exit the application',
        action: () => {
          // Exit should be handled gracefully by useCommandHandler
          throw new Error('Exit command should be handled by useCommandHandler');
        }
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
        // Re-throw to let the caller handle the error properly
        throw new Error(`Error executing ${commandName}: ${error.message}`);
      }
    } else {
      // This error will be handled by the caller (useCommandHandler)
      throw new Error(`Unknown command: ${commandName}. Type /help for available commands.`);
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