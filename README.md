# Dota 2 Damage Calculator

A Python GUI application for calculating total damage output in Dota 2, with dynamic rows, automatic calculations, and expression support.

## Features

- ✨ **Automatic Calculations** - No button pressing needed! Updates in real-time
- 🔢 **Expression Support** - Enter math expressions like `66*4` or `100+50`
- ➕ **Dynamic Rows** - Add or remove physical and magic damage rows on the fly
- 📊 **Line-by-Line Results** - See calculated damage for each individual row
- 🎯 **Separate Totals** - View physical total, magic total, and grand total
- 📜 **Scrollable Interface** - Add as many rows as you need

## Requirements

- Python 3.6 or higher
- tkinter (install with: `sudo pacman -S tk` on Arch Linux)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/dota-calculator-tool.git
cd dota-calculator-tool
```

2. Install tkinter if needed:
```bash
# Arch Linux / Manjaro
sudo pacman -S tk

# Ubuntu/Debian
sudo apt-get install python3-tk

# Fedora
sudo dnf install python3-tkinter
```

3. Run the application:
```bash
python dota_calculator.py
```

## Usage

### Basic Usage

1. **Enter Damage**: Type in raw damage or use expressions
   - Simple: `264`
   - Expression: `66*4` (will calculate to 264)
   - Complex: `(100+50)*2` (will calculate to 300)

2. **Enter Reduction**: Type the resistance percentage (0-100)

3. **View Results**: Each row shows its calculated damage automatically
   - Individual row results appear in green on the right
   - Section totals appear at the bottom of each section
   - Grand total appears in red at the bottom

### Adding/Removing Rows

- Click **"+ Add Row"** to add new physical or magic damage rows
- Click the **"✕"** button on any row to remove it
- Must keep at least one row of each type

### Examples

**Example 1: Auto attacks with spell**
- Physical #1: `66*4` with 25% reduction → `= 198.00`
- Magic #1: `300` with 29% reduction → `= 213.00`
- **Total: 411.00**

**Example 2: Multiple damage sources**
- Physical #1: `80*5` with 30% reduction → `= 280.00`
- Physical #2: `150` with 30% reduction → `= 105.00`
- Magic #1: `400` with 25% reduction → `= 300.00`
- Magic #2: `200+100` with 25% reduction → `= 225.00`
- **Total: 910.00**

## Features in Detail

### Expression Parser
Supports standard mathematical operations:
- Addition: `100+50`
- Subtraction: `200-50`
- Multiplication: `66*4`
- Division: `300/2`
- Parentheses: `(100+50)*2`
- Decimals: `66.5*4`

### Automatic Calculation
Every field change triggers instant recalculation:
- Type in damage field → updates immediately
- Change reduction percentage → recalculates instantly
- No need to click any buttons

### Dynamic Row Management
- Add unlimited rows for complex damage scenarios
- Each row is independent with its own reduction value
- Delete unwanted rows (minimum 1 per section maintained)

## Future Enhancements

- Pure damage type (ignores reductions)
- Critical strike multipliers
- Damage amplification/reduction modifiers
- Save/load damage profiles
- Export results to file
- Damage timeline/sequence
- Hero-specific calculations

## Contributing

Feel free to open issues or submit pull requests!

## License

MIT License