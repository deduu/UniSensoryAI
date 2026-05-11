/**
 * Static model registry derived from configs/models.yaml.
 * Updated at build time — no runtime fetch needed.
 *
 * Order matters: the first entry is the default for extraction
 * (Dashboard, Parse, Playground). Cloud models lead so first-time users
 * get the highest-accuracy option without local GPU setup.
 */
export const AVAILABLE_MODELS = [
  {
    id: 'gpt-4o',
    name: 'GPT-4o',
    provider: 'openai',
    providerLabel: 'OpenAI',
    type: 'cloud',
    capabilities: ['PDF', 'Images', 'Documents', 'Visual QA'],
    params: 'Cloud API',
    description: 'OpenAI flagship multimodal model via API.',
  },
  {
    id: 'gemini-2.0-flash',
    name: 'Gemini 2.0 Flash',
    provider: 'google',
    providerLabel: 'Google',
    type: 'cloud',
    capabilities: ['PDF', 'Images', 'Documents', 'Visual QA'],
    params: 'Cloud API',
    description: 'Google fast multimodal model via API.',
  },
  {
    id: 'qwen3-vl-30b',
    name: 'Qwen3-VL-30B-A3B-Instruct',
    provider: 'huggingface',
    providerLabel: 'Qwen',
    type: 'local',
    capabilities: ['PDF', 'Images', 'Documents'],
    params: '30B (A3B MoE)',
    description: 'High-accuracy vision-language model with MoE architecture.',
  },
  {
    id: 'qwen2-vl-2b-instruct',
    name: 'Qwen2-VL-2B-Instruct',
    provider: 'huggingface',
    providerLabel: 'Qwen',
    type: 'local',
    capabilities: ['PDF', 'Images', 'Documents'],
    params: '2B (4-bit quantized)',
    description: 'Lightweight quantized model for fast local inference.',
  },
  {
    id: 'lighton-ocr-2b',
    name: 'LightOnOCR-2-1B-base',
    provider: 'huggingface',
    providerLabel: 'LightOn',
    type: 'local',
    capabilities: ['OCR', 'PDF', 'Images'],
    params: '1B (4-bit quantized)',
    description: 'Specialized OCR model optimized for document text extraction.',
  },
  {
    id: 'llava-1.5-7b',
    name: 'LLaVA-1.5-7B',
    provider: 'huggingface',
    providerLabel: 'LLaVA',
    type: 'local',
    capabilities: ['Images', 'Visual QA'],
    params: '7B',
    description: 'General-purpose vision-language model for image understanding.',
  },
  {
    id: 'deepseek-vl2-small',
    name: 'DeepSeek-VL2-Small',
    provider: 'deepseek',
    providerLabel: 'DeepSeek',
    type: 'local',
    capabilities: ['PDF', 'Images', 'Documents'],
    params: 'Small',
    description: 'DeepSeek vision-language model for document analysis.',
  },
]
