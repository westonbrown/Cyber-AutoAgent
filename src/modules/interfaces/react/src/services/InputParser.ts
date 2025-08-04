/**
 * Smart Input Parser Service
 * Parses natural language input and converts to structured commands
 * Supports both natural language and guided flow commands
 */

export interface ParsedCommand {
  type: 'natural' | 'flow' | 'slash' | 'unknown';
  module?: string;
  target?: string;
  objective?: string;
  command?: string;
  args?: string[];
  confidence: number;
}


export class InputParser {
  // Available modules list - simplified
  private availableModules = [
    'general'
  ];

  // Common natural language patterns
  private commandPatterns = [
    {
      pattern: /^(?:scan|test|analyze|check|assess)\s+(.+?)(?:\s+(?:for|focusing\s+on|looking\s+for)\s+(.+))?$/i,
      type: 'scan' as const
    },
    {
      pattern: /^(?:audit|review|examine)\s+(.+?)(?:\s+(?:for|focusing\s+on)\s+(.+))?$/i,
      type: 'audit' as const
    },
    {
      pattern: /^(?:find|search\s+for|look\s+for)\s+(.+?)\s+(?:in|on|at)\s+(.+)$/i,
      type: 'search' as const
    }
  ];

  // Target patterns
  private targetPatterns = [
    { pattern: /^https?:\/\//, type: 'url' },
    { pattern: /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/, type: 'ip' },
    { pattern: /^[a-zA-Z0-9-]+\.[a-zA-Z]{2,}/, type: 'domain' },
    { pattern: /^\/|^\.\/|^~\//, type: 'path' },
    { pattern: /^[a-zA-Z]:\\/, type: 'windows_path' }
  ];

  constructor() {}

  // Main parsing method
  parse(input: string): ParsedCommand {
    const trimmedInput = input.trim();

    // Empty input
    if (!trimmedInput) {
      return { type: 'unknown', confidence: 0 };
    }

    // Slash commands
    if (trimmedInput.startsWith('/')) {
      return this.parseSlashCommand(trimmedInput);
    }

    // Flow commands (module, target, objective, execute)
    if (this.isFlowCommand(trimmedInput)) {
      return this.parseFlowCommand(trimmedInput);
    }

    // Natural language commands
    const naturalCommand = this.parseNaturalLanguage(trimmedInput);
    if (naturalCommand.confidence > 0.5) {
      return naturalCommand;
    }

    // Unknown command
    return { type: 'unknown', confidence: 0 };
  }

  // Parse slash commands
  private parseSlashCommand(input: string): ParsedCommand {
    const parts = input.slice(1).split(' ');
    const command = parts[0];
    const args = parts.slice(1);

    return {
      type: 'slash',
      command,
      args,
      confidence: 1.0
    };
  }

  // Check if input is a flow command
  private isFlowCommand(input: string): boolean {
    const flowKeywords = ['module', 'target', 'objective', 'execute', 'reset'];
    const firstWord = input.split(' ')[0].toLowerCase();
    return flowKeywords.includes(firstWord);
  }

  // Parse flow commands
  private parseFlowCommand(input: string): ParsedCommand {
    const parts = input.split(' ');
    const command = parts[0].toLowerCase();
    const value = parts.slice(1).join(' ');

    switch (command) {
      case 'module':
        return {
          type: 'flow',
          command: 'module',
          module: value,
          confidence: 1.0
        };
      case 'target':
        return {
          type: 'flow',
          command: 'target',
          target: value,
          confidence: 1.0
        };
      case 'objective':
        return {
          type: 'flow',
          command: 'objective',
          objective: value,
          confidence: 1.0
        };
      case 'execute':
        return {
          type: 'flow',
          command: 'execute',
          confidence: 1.0
        };
      case 'reset':
        return {
          type: 'flow',
          command: 'reset',
          confidence: 1.0
        };
      default:
        return { type: 'unknown', confidence: 0 };
    }
  }

  // Parse natural language commands - simplified without module detection
  private parseNaturalLanguage(input: string): ParsedCommand {
    // Try each command pattern for target extraction
    for (const pattern of this.commandPatterns) {
      const match = input.match(pattern.pattern);
      if (match) {
        const target = match[1];
        const objective = match[2] || '';
        
        // Don't detect module - use current module from context
        if (this.looksLikeTarget(target)) {
          return {
            type: 'natural',
            target: this.normalizeTarget(target),
            objective: objective || '',
            confidence: 0.8
          };
        }
      }
    }

    // Try simple patterns for target extraction
    const simpleMatch = this.parseSimplePatterns(input);
    if (simpleMatch.confidence > 0.5) {
      return simpleMatch;
    }

    return { type: 'unknown', confidence: 0 };
  }

  // Parse simple patterns like "scan example.com" - simplified without module detection
  private parseSimplePatterns(input: string): ParsedCommand {
    const words = input.toLowerCase().split(' ');
    
    // Look for action words
    const actionWords = ['scan', 'test', 'analyze', 'check', 'audit', 'review'];
    const hasAction = words.some(word => actionWords.includes(word));
    
    if (!hasAction) {
      return { type: 'unknown', confidence: 0 };
    }

    // Extract potential target
    const targets = words.filter(word => this.looksLikeTarget(word));
    
    if (targets.length === 0) {
      return { type: 'unknown', confidence: 0 };
    }

    const target = targets[0];
    
    return {
      type: 'natural',
      target: this.normalizeTarget(target),
      objective: '', // No default objective - let user specify if needed
      confidence: 0.7
    };
  }


  // Check if text looks like a target
  private looksLikeTarget(text: string): boolean {
    return this.targetPatterns.some(pattern => pattern.pattern.test(text));
  }

  // Check if text looks like a URL
  private looksLikeUrl(text: string): boolean {
    return /^https?:\/\//.test(text) || /^[a-zA-Z0-9-]+\.[a-zA-Z]{2,}/.test(text);
  }

  // Check if text looks like a path
  private looksLikePath(text: string): boolean {
    return /^\/|^\.\/|^~\/|^[a-zA-Z]:\\/.test(text);
  }

  // Normalize target format
  private normalizeTarget(target: string): string {
    // Add protocol if missing for domains
    if (/^[a-zA-Z0-9-]+\.[a-zA-Z]{2,}/.test(target) && !target.startsWith('http')) {
      return `https://${target}`;
    }
    return target;
  }


  // Get available modules
  getAvailableModules(): string[] {
    return this.availableModules;
  }

  // Get module description - simplified
  getModuleDescription(module: string): string {
    const descriptions: Record<string, string> = {
      general: 'General security assessment'
    };
    return descriptions[module] || 'Security assessment module';
  }
}