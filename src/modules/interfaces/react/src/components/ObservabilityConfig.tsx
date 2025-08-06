/**
 * Observability Configuration Component
 * 
 * Provides user-friendly configuration interface for Langfuse observability settings
 * with environment detection and deployment scenario handling.
 */

import React from 'react';
import { Config } from '../contexts/ConfigContext.js';

interface ObservabilityConfigProps {
  config: Config;
  onConfigChange: (updates: Partial<Config>) => void;
}

export const ObservabilityConfig: React.FC<ObservabilityConfigProps> = ({
  config,
  onConfigChange
}) => {
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-800">Observability & Tracing</h3>
      
      {/* Enable Observability */}
      <div className="flex items-center space-x-2">
        <input
          type="checkbox"
          id="observability"
          checked={config.observability}
          onChange={(e) => onConfigChange({ observability: e.target.checked })}
          className="h-4 w-4 text-blue-600"
        />
        <label htmlFor="observability" className="text-sm font-medium">
          Enable Langfuse Observability
        </label>
      </div>

      {config.observability && (
        <div className="ml-6 space-y-3 p-4 bg-gray-50 rounded-lg">
          {/* Langfuse Host Configuration */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Langfuse Host
            </label>
            <input
              type="text"
              value={config.langfuseHost || ''}
              onChange={(e) => onConfigChange({ langfuseHost: e.target.value })}
              placeholder="http://localhost:3000"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
            <p className="text-xs text-gray-500 mt-1">
              Default: Auto-detects Docker (langfuse-web:3000) vs Local (localhost:3000)
            </p>
          </div>

          {/* Host Override Option */}
          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              id="langfuseHostOverride"
              checked={config.langfuseHostOverride || false}
              onChange={(e) => onConfigChange({ langfuseHostOverride: e.target.checked })}
              className="h-4 w-4 text-blue-600"
            />
            <label htmlFor="langfuseHostOverride" className="text-sm">
              Force use configured host (disable auto-detection)
            </label>
          </div>

          {/* Environment Presets */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Quick Setup Presets
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                onClick={() => onConfigChange({
                  langfuseHost: 'http://localhost:3000',
                  langfuseHostOverride: false
                })}
                className="px-3 py-2 text-xs bg-blue-100 text-blue-800 rounded hover:bg-blue-200"
              >
                Local Dev
              </button>
              <button
                onClick={() => onConfigChange({
                  langfuseHost: 'http://langfuse-web:3000',
                  langfuseHostOverride: true
                })}
                className="px-3 py-2 text-xs bg-green-100 text-green-800 rounded hover:bg-green-200"
              >
                Docker Compose
              </button>
              <button
                onClick={() => onConfigChange({
                  langfuseHost: 'https://cloud.langfuse.com',
                  langfuseHostOverride: true
                })}
                className="px-3 py-2 text-xs bg-purple-100 text-purple-800 rounded hover:bg-purple-200"
              >
                Langfuse Cloud
              </button>
            </div>
          </div>

          {/* Authentication */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Public Key
              </label>
              <input
                type="text"
                value={config.langfusePublicKey || ''}
                onChange={(e) => onConfigChange({ langfusePublicKey: e.target.value })}
                placeholder="cyber-public"
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Secret Key
              </label>
              <input
                type="password"
                value={config.langfuseSecretKey || ''}
                onChange={(e) => onConfigChange({ langfuseSecretKey: e.target.value })}
                placeholder="cyber-secret"
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              />
            </div>
          </div>

          {/* Additional Options */}
          <details className="mt-4">
            <summary className="text-sm font-medium text-gray-700 cursor-pointer">
              Additional Settings
            </summary>
            <div className="mt-3 space-y-3 pl-4">
              {/* Prompt Management */}
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="enableLangfusePrompts"
                  checked={config.enableLangfusePrompts || false}
                  onChange={(e) => onConfigChange({ enableLangfusePrompts: e.target.checked })}
                  className="h-4 w-4 text-blue-600"
                />
                <label htmlFor="enableLangfusePrompts" className="text-sm">
                  Enable Langfuse Prompt Management
                </label>
              </div>

              {config.enableLangfusePrompts && (
                <div className="ml-6">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Prompt Label
                  </label>
                  <select
                    value={config.langfusePromptLabel || 'production'}
                    onChange={(e) => onConfigChange({ langfusePromptLabel: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                  >
                    <option value="production">Production</option>
                    <option value="staging">Staging</option>
                    <option value="development">Development</option>
                    <option value="testing">Testing</option>
                  </select>
                </div>
              )}
            </div>
          </details>
        </div>
      )}

      {/* Auto Evaluation */}
      <div className="flex items-center space-x-2">
        <input
          type="checkbox"
          id="autoEvaluation"
          checked={config.autoEvaluation}
          onChange={(e) => onConfigChange({ autoEvaluation: e.target.checked })}
          className="h-4 w-4 text-blue-600"
        />
        <label htmlFor="autoEvaluation" className="text-sm font-medium">
          Enable Automatic Evaluation (8 cybersecurity metrics)
        </label>
      </div>

      {config.autoEvaluation && (
        <div className="ml-6 p-4 bg-gray-50 rounded-lg">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Evaluation Model
            </label>
            <input
              type="text"
              value={config.evaluationModel || ''}
              onChange={(e) => onConfigChange({ evaluationModel: e.target.value })}
              placeholder="us.anthropic.claude-3-5-sonnet-20241022-v2:0"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
            <p className="text-xs text-gray-500 mt-1">
              Model used for scoring tool accuracy, evidence quality, methodology adherence, etc.
            </p>
          </div>
        </div>
      )}

      {/* Status Indicator */}
      <div className="flex items-center space-x-2 p-3 bg-blue-50 rounded-lg">
        <div className={`w-3 h-3 rounded-full ${config.observability ? 'bg-green-500' : 'bg-gray-400'}`} />
        <span className="text-sm text-blue-800">
          {config.observability 
            ? `✓ Observability enabled - traces will be sent to ${config.langfuseHostOverride ? config.langfuseHost : 'auto-detected host'}`
            : '○ Observability disabled - no tracing or evaluation'
          }
        </span>
      </div>
    </div>
  );
};