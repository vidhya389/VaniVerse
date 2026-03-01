# 🌾 VaniVerse - Voice-First AI Agricultural Advisory System

[![AWS](https://img.shields.io/badge/AWS-Lambda%20%7C%20Bedrock%20%7C%20S3-orange)](https://aws.amazon.com/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![Flutter](https://img.shields.io/badge/Flutter-3.x-02569B)](https://flutter.dev/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

VaniVerse is a serverless, voice-first AI assistant designed to bridge the digital divide for small-scale farmers in India. Built as the Proactive Voice-First Layer for Bharat-VISTAAR (India's 2026-27 digital agriculture roadmap), it provides hyper-local, expert-level agricultural advice in 8+ Indian languages.

## 🎯 Key Features

- **🎤 Voice-First Interface**: Natural conversation in Hindi, Tamil, Telugu, Kannada, Marathi, Bengali, Gujarati, and Punjabi
- **🧠 Proactive Engagement**: Remembers past issues and follows up automatically using AWS Bedrock Agent Memory
- **🌦️ Contextual Grounding**: Real-time weather data + land records + conversation history
- **⚡ Voice Response**: Optimized voice loop with parallel API calls
- **🔒 Safety Validation**: Chain-of-verification prevents harmful advice
- **📱 Low-Bandwidth Mode**: Works on 2G networks with audio compression
- **🌐 Multi-Agent Architecture**: Specialized agents for weather analytics and ICAR knowledge
- **🔐 Data Sovereignty**: All data stored in AWS Mumbai region with encryption

## 🏗️ Architecture

```
┌─────────────┐
│   Farmer    │ Speaks in regional language
│  (Mobile)   │
└──────┬──────┘
       │ Audio + GPS + Farmer ID
       ↓
┌────────────────────────────────────────────────────────┐
│                    AWS Lambda                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  1. Speech-to-Text (Google Speech API)           │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  2. Context Retrieval (Parallel)                 │  │
│  │     • Weather (OpenWeather API)                  │  │
│  │     • Land Records (UFSI/Mock)                   │  │
│  │     • Memory (Bedrock Agent)                     │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  3. LLM Inference (Bedrock Nova Lite)            │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  4. Specialized Agents (Parallel)                │  │
│  │     • Weather Analytics Agent                    │  │
│  │     • ICAR Knowledge Agent                       │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  5. Safety Validation                            │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  6. Text-to-Speech (Google TTS)                  │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
       │ Audio response
       ↓
┌─────────────┐
│   Farmer    │ Hears advice in their language
│  (Mobile)   │
└─────────────┘


```

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- AWS Account with configured credentials
- Google Cloud account (for Speech/TTS APIs)
- OpenWeather API key
- Flutter SDK (for mobile client)

### Backend Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/vaniverse.git
   cd vaniverse
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

   Required variables:
   ```env
   # AWS Configuration
   AWS_REGION=ap-south-1
   AUDIO_INPUT_BUCKET=your-input-bucket
   AUDIO_OUTPUT_BUCKET=your-output-bucket
   
   # AWS Bedrock
   BEDROCK_MODEL_ID=apac.amazon.nova-lite-v1:0
   BEDROCK_REGION=ap-south-1
   
   # Bedrock Agent Memory
   AGENTCORE_AGENT_ID=your-agent-id
   AGENTCORE_ALIAS_ID=your-alias-id
   AGENTCORE_MEMORY_ID=your-memory-id
   AGENTCORE_REGION=us-east-1
   
   # Google Cloud
   GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json
   
   # OpenWeather API
   OPENWEATHER_API_KEY=your-api-key
   ```

5. **Set up AWS infrastructure**
   ```bash
   python scripts/setup_infrastructure.py
   ```

6. **Deploy Lambda function**
   ```bash
   # Windows
   .\scripts\deploy_lambda_windows.ps1
   
   # Linux/Mac
   python scripts/deploy_lambda.py
   ```

### Mobile Client Setup
Quick start:
```bash
cd client
flutter pub get
flutter run
```

## 📁 Project Structure

```
vaniverse/
├── src/                          # Backend source code
│   ├── lambda_handler.py         # Main Lambda orchestrator
│   ├── agents/                   # Specialized agents
│   │   ├── orchestrator.py       # Multi-agent coordinator
│   │   ├── weather_analytics.py  # Weather analysis agent
│   │   └── icar_knowledge.py     # ICAR knowledge agent
│   ├── context/                  # Context retrieval
│   │   ├── retrieval.py          # Parallel context fetching
│   │   ├── weather.py            # OpenWeather integration
│   │   ├── memory.py             # Bedrock Agent Memory
│   │   ├── ufsi.py               # AgriStack integration
│   │   └── mock_ufsi.py          # Mock data for testing
│   ├── speech/                   # Speech processing
│   │   ├── google_speech.py      # Google Speech-to-Text
│   │   ├── google_tts.py         # Google Text-to-Speech
│   │   └── router.py             # Speech service router
│   ├── prompting/                # LLM prompting
│   │   └── builder.py            # Memory-first prompt builder
│   ├── safety/                   # Safety validation
│   │   └── validator.py          # Chain-of-verification
│   ├── models/                   # Data models
│   │   ├── context_data.py       # Context data structures
│   │   └── farmer_session.py     # Session management
│   └── utils/                    # Utilities
│       ├── retry.py              # Retry logic
│       ├── bandwidth.py          # Low-bandwidth handling
│       └── graceful_degradation.py
├── client/                       # Flutter mobile app
│   ├── lib/
│   │   ├── screens/              # UI screens
│   │   ├── services/             # Business logic
│   │   └── widgets/              # Reusable components
│   └── integration_test/         # Integration tests
├── tests/                        # Backend tests
│   ├── test_lambda_handler.py    # Handler tests
│   ├── test_agents.py            # Agent tests
│   ├── test_context.py           # Context tests
│   ├── test_speech.py            # Speech tests
│   └── test_integration_*.py     # Integration tests
├── scripts/                      # Deployment & utilities
│   ├── setup_infrastructure.py   # AWS setup
│   ├── deploy_lambda_windows.ps1 # Lambda deployment
│   ├── performance_benchmark.py  # Performance testing
│   └── test_bedrock_memory.py    # Memory testing
├── docs/                         # Documentation
│   ├── BEDROCK_AGENT_MEMORY_SETUP.md
│   ├── GOOGLE_SPEECH_SETUP.md
│   └── S3_TRIGGER_SETUP.md
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment template
└── README.md                     # This file
```

## 🧪 Testing

### Run Unit Tests
```bash
pytest tests/ -v
```

### Run Integration Tests
```bash
pytest tests/test_integration_*.py -v
```

### Run Performance Tests
```bash
# Integration performance tests
pytest tests/test_integration_performance.py -v -m performance

# Real-world benchmarks
python scripts/performance_benchmark.py --environment staging
```

### Run Property-Based Tests
```bash
pytest tests/test_*_property.py -v
```

## 📊 Performance Monitoring

### CloudWatch Dashboard

Deploy the performance dashboard:
```bash
aws cloudwatch put-dashboard \
  --dashboard-name VaniVerse-Performance \
  --dashboard-body file://cloudwatch_dashboard.json \
  --region ap-south-1
```

## 🔧 Configuration

### AWS Services Required

- **Lambda**: Serverless compute (512MB-1024MB memory)
- **S3**: Audio storage (2 buckets: input/output)
- **Bedrock**: Nova Lite 1 for LLM inference
- **Bedrock Agent**: Managed conversation memory
- **IAM**: Roles and policies for Lambda execution

### External APIs

- **Google Cloud Speech-to-Text**: Multi-language transcription
- **Google Cloud Text-to-Speech**: Natural voice synthesis
- **OpenWeather API**: Real-time weather data
- **UFSI (AgriStack)**: Farmer identity and land records (optional)

### Supported Languages

- Hindi (hi-IN)
- Tamil (ta-IN)
- Telugu (te-IN)
- Kannada (kn-IN)
- Marathi (mr-IN)
- Bengali (bn-IN)
- Gujarati (gu-IN)
- Punjabi (pa-IN)

## 🛠️ Development

### Local Testing

```bash
# Run Lambda handler locally
python -c "from src.lambda_handler import lambda_handler; lambda_handler(event, {})"

# Test specific components
python -m pytest tests/test_context.py -v
python -m pytest tests/test_agents.py -v
```

### Code Quality

```bash
# Run linter
pylint src/

# Format code
black src/ tests/

# Type checking
mypy src/
```

### Adding New Features

1. Create feature branch: `git checkout -b feature/your-feature`
2. Write tests first (TDD approach)
3. Implement feature
4. Run all tests: `pytest tests/ -v`
5. Update documentation
6. Submit pull request

## 📖 Documentation

- [Performance Report](PERFORMANCE_REPORT.md) - Detailed performance metrics and benchmarks
- [Performance Summary](PERFORMANCE_SUMMARY.md) - Quick performance reference
- [Performance Architecture](PERFORMANCE_ARCHITECTURE.md) - Visual architecture diagrams
- [Deployment Guide](DEPLOYMENT.md) - Production deployment instructions
- [Project Structure](PROJECT_STRUCTURE.md) - Detailed code organization
- [Client Setup](client/README.md) - Flutter app setup guide
- [Bedrock Agent Memory Setup](docs/BEDROCK_AGENT_MEMORY_SETUP.md) - Memory configuration
- [Google Speech Setup](docs/GOOGLE_SPEECH_SETUP.md) - Speech API configuration
- [S3 Trigger Setup](docs/S3_TRIGGER_SETUP.md) - S3 event configuration

## 🔐 Security

- **Data Encryption**: All data encrypted at rest (S3, Bedrock Agent) and in transit (TLS 1.3)
- **Data Sovereignty**: All farmer data stored in AWS Mumbai region (ap-south-1)
- **Access Control**: IAM roles with least-privilege permissions
- **API Security**: OAuth 2.0 for AgriStack/UFSI integration
- **Privacy**: Farmers can delete conversation history via voice command

## 🌍 Deployment

### Staging Environment

```bash
python scripts/deploy_staging.py
```

### Production Environment

```bash
# Deploy Lambda
python scripts/deploy_lambda.py --environment production

# Configure S3 trigger
python scripts/configure_s3_trigger.py --environment production

# Verify deployment
python scripts/validate_setup.py --environment production
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

## 🐛 Troubleshooting

### Common Issues

**Lambda timeout errors:**
- Increase Lambda timeout (default: 90s)
- Check external API response times
- Review CloudWatch logs

**Speech recognition failures:**
- Verify Google Cloud credentials
- Check audio file format (WAV, 16kHz, mono)
- Review language code configuration

**Memory retrieval issues:**
- Verify Bedrock Agent configuration
- Check AGENTCORE_MEMORY_ID in .env
- Review IAM permissions for cross-region access

**Performance issues:**
- Run performance benchmark: `python scripts/performance_benchmark.py`
- Check CloudWatch metrics
- Review parallel execution logs

See [PERFORMANCE_REPORT.md](PERFORMANCE_REPORT.md) for detailed troubleshooting guide.

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch
3. Write tests for new features
4. Ensure all tests pass
5. Submit a pull request

### Development Guidelines

- Follow PEP 8 style guide
- Write docstrings for all functions
- Add type hints where applicable
- Maintain test coverage > 80%
- Update documentation for new features

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **AWS**: For Bedrock, Lambda, and managed services
- **Google Cloud**: For Speech-to-Text and Text-to-Speech APIs
- **ICAR**: For agricultural research and guidelines
- **Bharat-VISTAAR**: For the vision of digital agriculture transformation
- **Indian Farmers**: For whom this system is built

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/vaniverse/issues)
- **Documentation**: [Wiki](https://github.com/yourusername/vaniverse/wiki)

## 🗺️ Roadmap

### Current (v1.0)
- ✅ Voice-first interface in 8 Indian languages
- ✅ Proactive engagement with memory
- ✅ Real-time weather integration
- ✅ Safety validation
- ✅ Low-bandwidth mode
- ✅ Multi-agent architecture

### Planned (v1.1)
- [ ] UFSI/AgriStack production integration
- [ ] Bhashini integration for additional languages
- [ ] Response caching for common questions
- [ ] CloudWatch alarms and monitoring
- [ ] Performance regression testing in CI/CD

### Future (v2.0)
- [ ] WebSocket support for streaming responses
- [ ] Predictive context pre-fetching
- [ ] Multi-region deployment
- [ ] CDN integration for audio delivery
- [ ] Mobile offline mode with local LLM

---

**Built with ❤️ for Indian farmers**

*Empowering agriculture through voice-first AI*
