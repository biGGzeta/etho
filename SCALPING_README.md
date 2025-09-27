# Scalping Enhancement Documentation

## Overview

This document describes the scalping enhancements added to the Etho trading bot. The enhancements transform the basic grid bot into a sophisticated scalping system capable of detecting and responding to short-term market movements.

## New Features

### 1. Enhanced Signal Detection

The bot now detects multiple types of market signals optimized for scalping:

- **SCALP_DOWN**: Micro-dump detection with rapid sell volume
- **SCALP_UP**: Micro-pump detection with rapid buy volume  
- **MOMENTUM_DOWN**: Bearish momentum based on price velocity
- **MOMENTUM_UP**: Bullish momentum based on price velocity
- **CALMA**: Low-activity periods for accumulation
- **DUMP**: Original dump detection (enhanced with faster response)

### 2. Adaptive Grid Construction

The bot now uses different grid strategies based on market signals:

- **Regular Grid**: Standard spacing for normal conditions
- **Scalping Grid**: Dense, adaptive grids for scalping opportunities
  - SCALP_DOWN: More levels with wider range to catch falling knives
  - SCALP_UP: Fewer levels, closer to price for quick entries
  - MOMENTUM signals: Optimized spacing based on direction
  - CALMA: Balanced grid for accumulation

### 3. ScalpingOrderManager

New order management system optimized for high-frequency trading:

- **Batch Order Placement**: Place multiple orders simultaneously
- **Stale Order Cleanup**: Automatically cancel old unfilled orders
- **Scalping TP Levels**: Tiered take-profit system
- **Order Tracking**: Detailed tracking of scalping orders

### 4. Configuration System

Comprehensive configuration for scalping parameters:

- **Risk Management**: Position limits, daily profit/loss targets
- **Timing**: Faster rebalancing for scalping signals
- **Grid Density**: Configurable grid multipliers
- **Take Profit**: Multi-level TP system with customizable ratios

## Configuration Files

### scalping_config.py

Main scalping configuration with parameters like:
- `SCALP_MODE`: Enable/disable scalping features
- `SCALP_REBALANCE_SECONDS`: Fast rebalancing interval
- `SCALP_TP_LEVELS`: Take profit level definitions
- `SCALP_MAX_CONCURRENT_ORDERS`: Risk management limits

### Enhanced config.py

Original configuration enhanced with scalping mode detection and parameter overrides when scalping is enabled.

## Usage

### Enable Scalping Mode

Set `SCALP_MODE = True` in `scalping_config.py` to activate all scalping features.

### Paper Mode Testing

The system fully supports paper mode for testing:

```bash
python test_scalping.py  # Run test suite
python bot.py            # Run bot in paper mode
```

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| SCALP_REBALANCE_SECONDS | 10 | Rebalance frequency for scalping |
| RAPID_TRADES_THRESHOLD | 15 | Trades needed to trigger scalp signals |
| MOMENTUM_THRESHOLD | 0.0005 | Price change threshold for momentum |
| SCALP_WINDOW_MS | 500 | Ultra-short analysis window |

## Signal Response Times

| Signal Type | Cooldown | Rebalance Speed | Grid Type |
|-------------|----------|-----------------|-----------|
| SCALP_DOWN | 1s | 3x faster | Dense, wide range |
| SCALP_UP | 1s | 3x faster | Sparse, close range |
| MOMENTUM_* | 0.7s | 3x faster | Adaptive |
| DUMP | 2s | 2x faster | Maximum spread |
| CALMA | 5s | Normal | Balanced |

## Risk Management

The scalping system includes multiple layers of risk management:

1. **Position Limits**: Maximum 60% of balance in scalping positions
2. **Order Timeouts**: Cancel stale orders after 3 minutes
3. **Daily Limits**: Stop trading at daily profit/loss thresholds
4. **Concurrent Orders**: Maximum 25 active orders
5. **Spread Filters**: Only trade within acceptable bid-ask spreads

## Performance

Expected improvements with scalping mode:

- **Signal Response**: 3-5x faster reaction to market changes
- **Opportunity Capture**: Better entry/exit timing on short-term moves
- **Risk Adjusted Returns**: Improved through faster position management
- **Order Fill Rate**: Higher due to better price placement

## Testing

Run the comprehensive test suite to validate all scalping features:

```bash
python test_scalping.py
```

The test suite validates:
- Signal detection accuracy
- Grid construction logic
- Order management functionality
- Configuration loading
- Bot integration
- Paper mode compatibility

## Monitoring

When scalping mode is active, the bot provides enhanced logging:

- Signal type and trigger conditions
- Grid type and density information
- Order batch placement results
- Stale order cleanup statistics
- Performance metrics

## Best Practices

1. **Start with Paper Mode**: Test thoroughly before live trading
2. **Monitor Spreads**: Ensure adequate liquidity for scalping
3. **Adjust Parameters**: Tune based on market conditions
4. **Risk Limits**: Set conservative daily limits initially
5. **Performance Review**: Regular analysis of scalping effectiveness

---

*Note: Scalping involves higher risk and requires more active monitoring than traditional grid trading. Ensure you understand the risks before enabling scalping mode.*