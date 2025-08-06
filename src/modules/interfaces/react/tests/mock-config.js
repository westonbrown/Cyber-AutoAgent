/**
 * Mock Configuration for Testing
 * 
 * Provides pre-configured state to skip setup wizard
 */

export const mockConfiguredState = {
  // Mark as configured
  isConfigured: true,
  hasSeenWelcome: true,
  
  // Model settings
  modelProvider: 'bedrock',
  modelId: 'us.anthropic.claude-sonnet-4-20250514-v1:0',
  awsRegion: 'us-east-1',
  awsBearerToken: process.env.AWS_BEARER_TOKEN_BEDROCK || 'test-token',
  
  // Container settings
  dockerImage: 'cyberautoagent:latest',
  dockerTimeout: 600,
  volumeMounts: [],
  
  // Operation settings  
  maxToolExecutions: 50,
  maxSwarmAgents: 3,
  memoryMode: 'auto',
  
  // Observability
  observability: {
    enabled: false,
    langfuseEnabled: false,
    evaluationEnabled: false
  },
  
  // Deployment
  deploymentMode: 'local-cli'
};

export const mockSetupState = {
  isConfigured: false,
  hasSeenWelcome: false
};