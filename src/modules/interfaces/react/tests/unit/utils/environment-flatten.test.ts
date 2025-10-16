import { flattenEnvironment } from '../../../src/utils/env.js';

describe('flattenEnvironment', () => {
  it('passes through simple key/value pairs', () => {
    const result = flattenEnvironment({ api_key: '123', region: 'us-east-1' });
    expect(result).toEqual({
      API_KEY: '123',
      REGION: 'us-east-1'
    });
  });

  it('flattens nested provider blocks', () => {
    const result = flattenEnvironment({
      deepseek_litellm: {
        provider: 'deepseek',
        base_url: 'https://api.deepseek.com/v1',
        model: 'deepseek-reasoner'
      }
    });

    expect(result).toEqual({
      DEEPSEEK_LITELLM_PROVIDER: 'deepseek',
      DEEPSEEK_LITELLM_BASE_URL: 'https://api.deepseek.com/v1',
      DEEPSEEK_LITELLM_MODEL: 'deepseek-reasoner'
    });
  });

  it('stringifies boolean, number, and array values', () => {
    const result = flattenEnvironment({
      feature_flags: {
        enabled: true,
        retry_limit: 3,
        models: ['a', 'b']
      }
    });

    expect(result).toEqual({
      FEATURE_FLAGS_ENABLED: 'true',
      FEATURE_FLAGS_RETRY_LIMIT: '3',
      FEATURE_FLAGS_MODELS: JSON.stringify(['a', 'b'])
    });
  });
});
