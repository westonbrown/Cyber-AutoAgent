/**
 * Module Context for Cyber-AutoAgent
 * Manages security modules and their capabilities
 */

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import * as fs from 'fs/promises';
import * as path from 'path';
import * as yaml from 'js-yaml';

export interface ModuleTool {
  name: string;
  description: string;
  category: string;
}

export interface ModuleInfo {
  name: string;
  description: string;
  category: string;
  tools: ModuleTool[];
  capabilities: string[];
  reportFormat?: string;
}

export interface ModuleContextType {
  currentModule: string;
  availableModules: Record<string, ModuleInfo>;
  moduleInfo?: ModuleInfo;
  switchModule: (moduleName: string) => Promise<void>;
  suggestModuleForObjective: (objective: string) => string;
  isLoading: boolean;
  error?: string;
}

const ModuleContext = createContext<ModuleContextType | undefined>(undefined);

// Module keyword mappings for smart suggestions
const MODULE_KEYWORDS: Record<string, string[]> = {
  general: ['general', 'comprehensive', 'security', 'assessment', 'pentest', 'scan', 'vulnerability', 'recon']
};

export const ModuleProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentModule, setCurrentModule] = useState<string>('general');
  const [availableModules, setAvailableModules] = useState<Record<string, ModuleInfo>>({});
  const [moduleInfo, setModuleInfo] = useState<ModuleInfo>();
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>();

  // Load all available modules on mount
  useEffect(() => {
    loadAvailableModules();
  }, []);

  const loadAvailableModules = async () => {
    try {
      // The React app is located at: src/modules/interfaces/react
      // The operation_plugins are at: src/modules/operation_plugins
      // So we need to go up 2 directories from the react folder
      const modulesDir = path.resolve(process.cwd(), '..', '..', 'operation_plugins');
      
      // Debug logging for module discovery
      if (process.env.DEBUG) {
        console.log('[ModuleContext] Looking for modules in:', modulesDir);
      }
      const entries = await fs.readdir(modulesDir, { withFileTypes: true });
      
      const modules: Record<string, ModuleInfo> = {};
      
      for (const entry of entries) {
        if (entry.isDirectory()) {
          const moduleInfo = await loadModuleInfo(entry.name);
          if (moduleInfo) {
            modules[entry.name] = moduleInfo;
          }
        }
      }
      
      setAvailableModules(modules);
      
      // Load default module
      if (modules.general) {
        setModuleInfo(modules.general);
      }
    } catch (err) {
      console.error('Failed to load modules:', err);
      setError('Failed to load security modules');
    }
  };

  const loadModuleInfo = async (moduleName: string): Promise<ModuleInfo | null> => {
    try {
      // Use the same relative path as loadAvailableModules
      const modulePath = path.resolve(process.cwd(), '..', '..', 'operation_plugins', moduleName);
      const yamlPath = path.join(modulePath, 'module.yaml');
      
      // Check if module.yaml exists
      try {
        await fs.access(yamlPath);
      } catch {
        // If no YAML, create basic info
        return {
          name: moduleName,
          description: `${moduleName.replace(/_/g, ' ')} module`,
          category: 'security',
          tools: [],
          capabilities: []
        };
      }
      
      const yamlContent = await fs.readFile(yamlPath, 'utf-8');
      const moduleConfig = yaml.load(yamlContent) as any;
      
      // Load tools from tools directory
      const tools: ModuleTool[] = [];
      const toolsDir = path.join(modulePath, 'tools');
      
      try {
        const toolFiles = await fs.readdir(toolsDir);
        for (const toolFile of toolFiles) {
          if (toolFile.endsWith('.py')) {
            const toolName = toolFile.replace('.py', '');
            tools.push({
              name: toolName,
              description: moduleConfig.tools?.[toolName]?.description || toolName,
              category: moduleConfig.tools?.[toolName]?.category || 'general'
            });
          }
        }
      } catch {
        // Tools directory might not exist
      }
      
      return {
        name: moduleName,
        description: moduleConfig.description || `${moduleName} module`,
        category: moduleConfig.category || 'security',
        tools,
        capabilities: moduleConfig.capabilities || [],
        reportFormat: moduleConfig.report_format
      };
    } catch (err) {
      console.error(`Failed to load module ${moduleName}:`, err);
      return null;
    }
  };

  const switchModule = useCallback(async (moduleName: string) => {
    if (!availableModules[moduleName]) {
      setError(`Module ${moduleName} not found`);
      return;
    }
    
    setIsLoading(true);
    setError(undefined);
    
    try {
      setCurrentModule(moduleName);
      setModuleInfo(availableModules[moduleName]);
    } catch (err) {
      setError(`Failed to switch to module ${moduleName}`);
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [availableModules]);

  const suggestModuleForObjective = useCallback((objective: string): string => {
    const objectiveLower = objective.toLowerCase();
    
    // Check each module's keywords
    for (const [module, keywords] of Object.entries(MODULE_KEYWORDS)) {
      for (const keyword of keywords) {
        if (objectiveLower.includes(keyword)) {
          return module;
        }
      }
    }
    
    // Default suggestions based on common patterns
    // All objectives default to general module
    return 'general';
  }, []);

  const value: ModuleContextType = {
    currentModule,
    availableModules,
    moduleInfo,
    switchModule,
    suggestModuleForObjective,
    isLoading,
    error
  };

  return (
    <ModuleContext.Provider value={value}>
      {children}
    </ModuleContext.Provider>
  );
};

export const useModule = () => {
  const context = useContext(ModuleContext);
  if (!context) {
    throw new Error('useModule must be used within ModuleProvider');
  }
  return context;
};