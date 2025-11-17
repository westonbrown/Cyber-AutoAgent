/**
 * Module Context for Cyber-AutoAgent
 * Manages security modules and their capabilities
 */

import React, { createContext, useContext, useState, useCallback, useEffect, useMemo } from 'react';
import * as fs from 'fs/promises';
import { existsSync } from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';
import { loggingService } from '../services/LoggingService.js';

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

export const ModuleProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentModule, setCurrentModule] = useState<string>('');
  const [availableModules, setAvailableModules] = useState<Record<string, ModuleInfo>>({});
  const [moduleInfo, setModuleInfo] = useState<ModuleInfo>();
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>();

  const loadAvailableModules = useCallback(async () => {
    try {
      // The React app is located at: src/modules/interfaces/react
      // The operation_plugins are at: src/modules/operation_plugins
      // In Docker: process.cwd() = /app, so we need src/modules/operation_plugins
      // In dev: process.cwd() might be the react folder, so handle both cases
      const isDocker = process.env.CONTAINER === 'docker' || existsSync('/app/src/modules');
      const modulesDir = isDocker
        ? path.resolve('/app/src/modules/operation_plugins')
        : path.resolve(process.cwd(), '..', '..', 'operation_plugins');
      
      // Debug logging for module discovery
      if (process.env.DEBUG) {
        loggingService.info('[ModuleContext] Looking for modules in:', modulesDir);
      }
      
      // Check if directory exists first
      try {
        await fs.access(modulesDir);
      } catch {
        // Directory doesn't exist yet - this is normal for new installations
        // Don't log errors, just set empty modules
        setAvailableModules({});
        return;
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
      
      // PREVENT UNNECESSARY UPDATES: Check if modules actually changed
      setAvailableModules(prevModules => {
        const prevStr = JSON.stringify(prevModules);
        const newStr = JSON.stringify(modules);
        if (prevStr === newStr) {
          return prevModules; // Return same reference to prevent re-renders
        }
        return modules;
      });
      
      // Load default module - use first available if general doesn't exist
      const moduleNames = Object.keys(modules);
      if (moduleNames.length > 0) {
        const defaultModule = modules.general || modules[moduleNames[0]];
        const defaultModuleName = modules.general ? 'general' : moduleNames[0];
        setCurrentModule(defaultModuleName);
        setModuleInfo(defaultModule);
      }
    } catch (err) {
      // Only log in debug mode - don't show errors to users
      if (process.env.DEBUG) {
        loggingService.error('Failed to load modules:', err);
      }
      // Silently handle the error - modules are optional
      setAvailableModules({});
    }
  }, []); // Empty dependencies - only changes when component mounts

  // Load all available modules on mount
  useEffect(() => {
    loadAvailableModules();
  }, [loadAvailableModules]);

  const loadModuleInfo = async (moduleName: string): Promise<ModuleInfo | null> => {
    try {
      // Use the same path logic as loadAvailableModules
      const isDocker = process.env.CONTAINER === 'docker' || existsSync('/app/src/modules');
      const modulePath = isDocker
        ? path.resolve('/app/src/modules/operation_plugins', moduleName)
        : path.resolve(process.cwd(), '..', '..', 'operation_plugins', moduleName);
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
      // Only log in debug mode
      if (process.env.DEBUG) {
        loggingService.error(`Failed to load module ${moduleName}:`, err);
      }
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
      loggingService.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [availableModules]);

  const suggestModuleForObjective = useCallback((objective: string): string => {
    const objectiveLower = objective.toLowerCase();
    
    // Check each available module's capabilities and description for matches
    for (const [moduleName, moduleInfo] of Object.entries(availableModules)) {
      // Check module description
      if (moduleInfo.description.toLowerCase().includes(objectiveLower)) {
        return moduleName;
      }
      
      // Check module capabilities
      for (const capability of moduleInfo.capabilities) {
        if (objectiveLower.includes(capability.toLowerCase()) || 
            capability.toLowerCase().includes(objectiveLower)) {
          return moduleName;
        }
      }
    }
    
    // Default to general module if available, otherwise first available module
    if (availableModules.general) {
      return 'general';
    }
    
    const moduleNames = Object.keys(availableModules);
    return moduleNames.length > 0 ? moduleNames[0] : 'general';
  }, [availableModules]);

  // Use useMemo to prevent infinite re-renders
  // Without this, the value object gets recreated on every render, causing all consumers to re-render
  const value: ModuleContextType = useMemo(() => ({
    currentModule,
    availableModules,
    moduleInfo,
    switchModule,
    suggestModuleForObjective,
    isLoading,
    error
  }), [currentModule, availableModules, moduleInfo, switchModule, suggestModuleForObjective, isLoading, error]);

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