# AIropa Automation Layer

AIropa is an AI-powered automation framework designed to streamline and automate complex workflows.

## 🚀 Quick Start

### Prerequisites
- Python 3.7+
- SQLite (included with Python)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-repo/airopa-automation.git
cd airopa-automation

# Install dependencies
pip install -r requirements.txt

# Run the demo
python main.py
```

## 📦 Features

- **Agent Framework**: Base classes for creating custom automation agents
- **Configuration Management**: Flexible configuration system with file and environment variable support
- **Database Integration**: SQLite support with easy extensibility to other databases
- **Task Management**: Track and manage automation tasks and their execution history

## 🏗️ Architecture

```
airopa-automation/
├── airopa_automation/          # Core package
│   ├── __init__.py            # Package initialization
│   ├── agents.py              # Agent base classes
│   ├── config.py              # Configuration management
│   └── database.py            # Database operations
├── database/                  # Database files
│   └── schema.sql             # Database schema
├── main.py                    # Main entry point
├── README.md                  # Documentation
└── requirements.txt           # Dependencies
```

## 🤖 Creating Agents

```python
from airopa_automation.agents import BaseAgent

class MyCustomAgent(BaseAgent):
    def execute(self, *args, **kwargs):
        # Your automation logic here
        return {"status": "completed", "result": "success"}

# Usage
agent = MyCustomAgent(name="my_agent", description="My custom automation agent")
result = agent.execute(task_data)
```

## 🔧 Configuration

Create a `config.json` file:

```json
{
  "debug": true,
  "log_level": "DEBUG",
  "database": {
    "type": "sqlite",
    "path": "database/airopa.db"
  },
  "agents": {
    "default_timeout": 120
  }
}
```

Or use environment variables:

```bash
export AIROPA_DEBUG=true
export AIROPA_DATABASE__TYPE=sqlite
export AIROPA_DATABASE__PATH=database/airopa.db
```

## 📊 Database

The system includes a SQLite database with tables for:
- Tasks (automation tasks)
- Task executions (execution history)
- Agents (registered automation agents)

## 🎯 Roadmap

- [x] Core agent framework
- [x] Configuration management
- [x] Database integration
- [ ] Advanced agent types
- [ ] Web interface
- [ ] API endpoints
- [ ] Scheduling system

## 🤝 Contributing

Contributions are welcome! Please open issues and pull requests.

## 📄 License

MIT License - see LICENSE file for details.