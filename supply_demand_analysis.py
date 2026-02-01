#!/usr/bin/env python3
"""
Supply/Demand Analysis Framework

Economic principle: Price is ultimately determined by supply and demand equilibrium.
- Short-term: Speculation creates price deviations ("voting machine")
- Long-term: Fundamentals prevail ("weighing machine") - Buffett/Munger

This module provides frameworks for analyzing:
1. Historical commodity supply/demand case studies
2. Forward-looking commodity analysis (silver, uranium, copper)
3. Bitcoin fundamental valuation models

Key insight: Commodities are more "calculable" than stocks because:
- Supply constraints are visible (mining capacity, reserves, production costs)
- Demand is predictable (industrial commitments, infrastructure investments)
- No execution risk from management teams
"""

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import json
import math


# =============================================================================
# SECTION 1: HISTORICAL CASE STUDIES
# =============================================================================

@dataclass
class SupplyDemandEvent:
    """Represents a historical supply/demand imbalance event"""
    name: str
    commodity: str
    start_year: int
    end_year: int
    price_change_pct: float
    supply_factor: str
    demand_factor: str
    predictability_score: float  # 1-10, how predictable was this?
    key_indicators: List[str]
    lessons: List[str]


HISTORICAL_CASE_STUDIES = [
    # 1970s Oil Crisis
    SupplyDemandEvent(
        name="1973 Oil Crisis (OPEC Embargo)",
        commodity="Crude Oil",
        start_year=1973,
        end_year=1974,
        price_change_pct=300,  # $3 to $12/barrel
        supply_factor="OPEC embargo on US/allies supporting Israel in Yom Kippur War",
        demand_factor="Post-war industrial expansion, car-dependent US economy",
        predictability_score=7,
        key_indicators=[
            "Middle East tensions escalating months before",
            "OPEC gaining coordination power (formed 1960)",
            "US oil production peaked in 1970 (Hubbert's Peak)",
            "Global oil demand growing 7%/year",
            "Strategic Petroleum Reserve did not exist yet"
        ],
        lessons=[
            "Geopolitical supply disruptions are predictable if you watch tensions",
            "Concentrated supply (OPEC 55% of world oil) creates vulnerability",
            "Inelastic demand (no substitutes) amplifies price moves",
            "Infrastructure takes years to adjust (can't build refineries overnight)"
        ]
    ),

    # 1979 Oil Crisis
    SupplyDemandEvent(
        name="1979 Oil Crisis (Iranian Revolution)",
        commodity="Crude Oil",
        start_year=1979,
        end_year=1980,
        price_change_pct=150,  # $14 to $35/barrel
        supply_factor="Iranian Revolution removed 4M barrels/day from market",
        demand_factor="Still high from post-embargo demand, cold winter 1978-79",
        predictability_score=6,
        key_indicators=[
            "Iranian protests began in 1978",
            "Shah's regime visibly weakening",
            "Oil workers went on strike",
            "Iran was #2 OPEC producer",
            "Panic buying created artificial shortage"
        ],
        lessons=[
            "Political instability in major producers = supply risk",
            "Market psychology (panic) can amplify fundamental shortages",
            "Second-order effects: Iraq-Iran war further disrupted supply"
        ]
    ),

    # 2000s Commodity Supercycle
    SupplyDemandEvent(
        name="2000s Commodity Supercycle",
        commodity="Broad Commodities (Oil, Copper, Iron Ore)",
        start_year=2002,
        end_year=2008,
        price_change_pct=400,  # CRB Index quadrupled
        supply_factor="Underinvestment in 1990s (low prices), long lead times for new mines",
        demand_factor="China's WTO entry (2001), massive infrastructure buildout",
        predictability_score=8,
        key_indicators=[
            "China's WTO accession (Dec 2001) was public knowledge",
            "China GDP growing 10%+/year",
            "Mine depletion rates accelerating",
            "New mine development takes 7-10 years",
            "Urbanization of 300M people announced"
        ],
        lessons=[
            "Infrastructure demand is predictable years in advance",
            "Supply response has LONG lead times (mining, refining)",
            "Population/urbanization trends are knowable",
            "This was the most predictable supercycle in modern history"
        ]
    ),

    # Silver in 2010-2011
    SupplyDemandEvent(
        name="2010-2011 Silver Rally",
        commodity="Silver",
        start_year=2010,
        end_year=2011,
        price_change_pct=170,  # $17 to $49/oz
        supply_factor="Mine supply flat for decade, 70% is byproduct of other mining",
        demand_factor="Solar panel growth, industrial use, investment demand (QE fears)",
        predictability_score=5,
        key_indicators=[
            "Solar installations growing 40%+/year",
            "Silver ETFs launched (SLV 2006)",
            "Fed QE programs announced",
            "Industrial demand growing 4%/year",
            "Above-ground stocks declining"
        ],
        lessons=[
            "Silver is unique: both industrial AND monetary metal",
            "Byproduct supply is inelastic (can't just mine more silver)",
            "Investment demand can overwhelm industrial fundamentals",
            "Price crashed 35% in 5 days (May 2011) - speculation cuts both ways"
        ]
    ),

    # Uranium 2003-2007
    SupplyDemandEvent(
        name="Uranium Bull Market 2003-2007",
        commodity="Uranium",
        start_year=2003,
        end_year=2007,
        price_change_pct=1400,  # $10 to $140/lb
        supply_factor="Post-Soviet underinvestment, Cigar Lake flood (2006)",
        demand_factor="Nuclear renaissance narrative, China/India reactor buildout",
        predictability_score=7,
        key_indicators=[
            "Secondary supply (warhead downblending) known to end",
            "HEU Agreement ending 2013 (announced years ahead)",
            "New reactor construction announcements",
            "Kazakhstan becoming major producer (knowable)",
            "Mine production < reactor demand for 20 years"
        ],
        lessons=[
            "Uranium has longest supply response time (10-15 years for new mines)",
            "Secondary supply endings are SCHEDULED and public",
            "Fukushima (2011) shows demand can collapse unexpectedly",
            "Cyclicality extreme: $140 → $18 → now recovering"
        ]
    ),

    # Copper 2020-2022
    SupplyDemandEvent(
        name="Copper Rally 2020-2022",
        commodity="Copper",
        start_year=2020,
        end_year=2022,
        price_change_pct=100,  # $2.50 to $5.00/lb
        supply_factor="COVID disrupted Chile/Peru mining, grade declining at major mines",
        demand_factor="EV transition (3-4x copper per vehicle), renewable energy buildout",
        predictability_score=9,
        key_indicators=[
            "EV adoption curves published by all major automakers",
            "Government EV mandates with specific dates",
            "Solar/wind installations require 5x more copper than fossil",
            "No major new copper discoveries in 20 years",
            "Average mine grade declining 25% per decade",
            "New mine development: 15-20 years from discovery to production"
        ],
        lessons=[
            "Energy transition copper demand is the most calculable thesis ever",
            "Supply constraints are geological (can't create more copper)",
            "This thesis is still early (2020s-2030s)",
            "Chile (28% of supply) has water/political constraints"
        ]
    ),
]


def print_case_study(event: SupplyDemandEvent):
    """Pretty print a case study"""
    print(f"\n{'='*70}")
    print(f"CASE STUDY: {event.name}")
    print(f"{'='*70}")
    print(f"Commodity: {event.commodity}")
    print(f"Period: {event.start_year} - {event.end_year}")
    print(f"Price Change: +{event.price_change_pct}%")
    print(f"Predictability Score: {event.predictability_score}/10")
    print(f"\n📉 SUPPLY FACTOR:")
    print(f"   {event.supply_factor}")
    print(f"\n📈 DEMAND FACTOR:")
    print(f"   {event.demand_factor}")
    print(f"\n🔍 KEY LEADING INDICATORS:")
    for ind in event.key_indicators:
        print(f"   • {ind}")
    print(f"\n💡 LESSONS LEARNED:")
    for lesson in event.lessons:
        print(f"   • {lesson}")


def analyze_all_case_studies():
    """Analyze patterns across all case studies"""
    print("\n" + "="*70)
    print("SUPPLY/DEMAND CASE STUDY ANALYSIS")
    print("="*70)

    for event in HISTORICAL_CASE_STUDIES:
        print_case_study(event)

    # Summary statistics
    print("\n" + "="*70)
    print("PATTERN ANALYSIS")
    print("="*70)

    scores = [e.predictability_score for e in HISTORICAL_CASE_STUDIES]
    changes = [e.price_change_pct for e in HISTORICAL_CASE_STUDIES]
    avg_predictability = sum(scores) / len(scores)
    avg_price_change = sum(changes) / len(changes)

    print(f"\nAverage Predictability Score: {avg_predictability:.1f}/10")
    print(f"Average Price Change: +{avg_price_change:.0f}%")

    print("\n📊 COMMON PATTERNS IN PREDICTABLE SUPPLY/DEMAND IMBALANCES:")
    patterns = [
        "1. Supply constraints are STRUCTURAL (geology, infrastructure, regulation)",
        "2. Demand drivers are COMMITTED (government mandates, infrastructure investments)",
        "3. Lead times create LAGS (years between price signal and supply response)",
        "4. Concentrated supply creates VULNERABILITY (few countries/companies)",
        "5. Inelastic demand means NO SUBSTITUTES (critical industrial uses)",
        "6. Information is PUBLIC (reactor orders, EV mandates, mine depletion)"
    ]
    for p in patterns:
        print(f"   {p}")


# =============================================================================
# SECTION 2: COMMODITY SUPPLY/DEMAND MODELS
# =============================================================================

@dataclass
class CommodityFundamentals:
    """Fundamental supply/demand data for a commodity"""
    name: str
    symbol: str
    current_price: float
    unit: str

    # Supply factors
    annual_production: float  # units/year
    production_growth_rate: float  # %/year
    known_reserves: float  # total units
    years_of_reserves: float
    production_cost_avg: float  # $/unit
    production_cost_marginal: float  # $/unit for new production
    supply_concentration: Dict[str, float]  # country: % of supply
    new_supply_lead_time_years: float

    # Demand factors
    annual_consumption: float  # units/year
    demand_growth_rate: float  # %/year
    demand_by_sector: Dict[str, float]  # sector: % of demand
    demand_elasticity: float  # -1 to 0 (inelastic to elastic)

    # Inventory/Balance
    above_ground_stocks: float  # units
    days_of_consumption: float
    market_balance: float  # surplus (+) or deficit (-)

    # Forward-looking
    committed_demand_projects: List[str]
    known_supply_constraints: List[str]
    catalyst_events: List[Tuple[str, str]]  # (date, event)


# Current commodity data (as of early 2025)
SILVER_FUNDAMENTALS = CommodityFundamentals(
    name="Silver",
    symbol="SI=F",
    current_price=30.0,  # $/oz
    unit="oz",

    # Supply
    annual_production=820_000_000,  # 820M oz
    production_growth_rate=1.5,
    known_reserves=550_000_000_000,  # 550B oz (in-ground)
    years_of_reserves=45,
    production_cost_avg=15.0,
    production_cost_marginal=22.0,
    supply_concentration={
        "Mexico": 24,
        "China": 13,
        "Peru": 12,
        "Chile": 6,
        "Russia": 5,
        "Other": 40
    },
    new_supply_lead_time_years=7,

    # Demand
    annual_consumption=1_100_000_000,  # 1.1B oz (DEFICIT!)
    demand_growth_rate=5.0,  # driven by solar
    demand_by_sector={
        "Industrial": 55,  # electronics, solar, medical
        "Solar PV": 20,  # fastest growing
        "Photography": 3,
        "Jewelry": 17,
        "Investment": 5
    },
    demand_elasticity=-0.3,  # quite inelastic

    # Inventory
    above_ground_stocks=1_500_000_000,  # 1.5B oz
    days_of_consumption=500,
    market_balance=-280_000_000,  # 280M oz DEFICIT per year

    # Forward-looking
    committed_demand_projects=[
        "IEA: Solar installations to triple by 2030",
        "EU Green Deal: 40% renewable by 2030",
        "US IRA: $369B clean energy investment",
        "China: 1,200 GW solar target by 2030",
        "India: 500 GW renewable by 2030"
    ],
    known_supply_constraints=[
        "70% of silver is byproduct of zinc/lead/copper mining",
        "Cannot increase silver production without increasing base metal mining",
        "Mexico labor/water issues",
        "Average ore grade declining 2%/year",
        "No major discoveries in past decade"
    ],
    catalyst_events=[
        ("2025-2030", "Solar demand to exceed 300M oz/year (from 150M)"),
        ("2026", "EV adoption acceleration (silver in electronics)"),
        ("2027", "India solar buildout peak demand"),
        ("2030", "Potential depletion of above-ground stocks at current deficit")
    ]
)


URANIUM_FUNDAMENTALS = CommodityFundamentals(
    name="Uranium",
    symbol="URA",  # ETF proxy
    current_price=85.0,  # $/lb U3O8
    unit="lb",

    # Supply
    annual_production=130_000_000,  # 130M lbs
    production_growth_rate=2.0,
    known_reserves=7_900_000_000,  # 7.9B lbs identified
    years_of_reserves=40,
    production_cost_avg=40.0,
    production_cost_marginal=65.0,  # New mines need $65+
    supply_concentration={
        "Kazakhstan": 43,
        "Canada": 15,
        "Namibia": 11,
        "Australia": 9,
        "Uzbekistan": 7,
        "Other": 15
    },
    new_supply_lead_time_years=15,  # LONGEST of any commodity

    # Demand
    annual_consumption=180_000_000,  # 180M lbs for reactors
    demand_growth_rate=3.5,
    demand_by_sector={
        "Nuclear Power": 95,
        "Research Reactors": 3,
        "Medical Isotopes": 2
    },
    demand_elasticity=-0.9,  # EXTREMELY inelastic - reactors must run

    # Inventory
    above_ground_stocks=400_000_000,  # utility inventories depleted
    days_of_consumption=800,  # but declining
    market_balance=-50_000_000,  # 50M lb DEFICIT per year

    committed_demand_projects=[
        "63 reactors under construction globally (IEA)",
        "China: 150 new reactors by 2035",
        "US: Vogtle 3&4 online, license extensions",
        "Japan: Reactor restarts accelerating",
        "SMR development: NuScale, TerraPower, X-energy",
        "France: 14 new reactors announced"
    ],
    known_supply_constraints=[
        "Secondary supply (warhead downblending) ENDED 2013",
        "Kazatomprom production cuts 2022-2024",
        "Niger coup (5% of supply) - uncertain",
        "Cigar Lake (largest mine) depleting",
        "New mines need $65+/lb to be economic",
        "Permitting takes 10+ years in Western countries"
    ],
    catalyst_events=[
        ("2024-2025", "Utility restocking cycle beginning"),
        ("2026", "First SMRs potentially operational"),
        ("2027-2030", "China reactor buildout peaks"),
        ("2030", "Secondary supply fully depleted"),
        ("2035", "Global nuclear capacity +25% from today")
    ]
)


COPPER_FUNDAMENTALS = CommodityFundamentals(
    name="Copper",
    symbol="HG=F",
    current_price=4.20,  # $/lb
    unit="lb",

    # Supply
    annual_production=22_000_000_000,  # 22M tonnes = 48.5B lbs
    production_growth_rate=2.0,
    known_reserves=880_000_000_000,  # 880M tonnes = 1.9T lbs
    years_of_reserves=40,
    production_cost_avg=2.50,
    production_cost_marginal=4.00,
    supply_concentration={
        "Chile": 27,
        "Peru": 10,
        "China": 8,
        "DRC": 8,
        "USA": 5,
        "Other": 42
    },
    new_supply_lead_time_years=16,  # discovery to production

    # Demand
    annual_consumption=25_000_000_000,  # 25M tonnes growing
    demand_growth_rate=4.0,  # EV + renewable driven
    demand_by_sector={
        "Construction": 28,
        "Electronics": 21,
        "Transportation": 13,
        "Industrial": 11,
        "EVs": 10,  # growing fast
        "Renewable Energy": 9,  # growing fast
        "Other": 8
    },
    demand_elasticity=-0.4,

    above_ground_stocks=500_000_000,  # exchange inventories
    days_of_consumption=7,  # VERY tight
    market_balance=-3_000_000_000,  # growing deficit

    committed_demand_projects=[
        "EV: Each EV uses 180 lbs copper vs 50 lbs for ICE",
        "Solar: 5 tonnes copper per MW",
        "Wind: 4 tonnes copper per MW (onshore), 15 tonnes (offshore)",
        "Grid: $2T global grid investment needed",
        "Data Centers: AI boom driving power infrastructure",
        "All automakers committed to 50%+ EV by 2030"
    ],
    known_supply_constraints=[
        "No major discovery in 20 years",
        "Chile water restrictions (Escondida)",
        "Average ore grade declined 30% since 2000",
        "DRC political risk",
        "Peru protests disrupting operations",
        "Project pipeline way below demand growth"
    ],
    catalyst_events=[
        ("2025", "Copper deficit widens as EV production scales"),
        ("2027", "IEA projects 6M tonne deficit possible"),
        ("2030", "Energy transition requires 50% more copper"),
        ("2035", "Goldman: copper could hit $15,000/tonne")
    ]
)


def analyze_commodity_fundamentals(commodity: CommodityFundamentals) -> Dict:
    """
    Analyze supply/demand balance and calculate fair value indicators
    """
    analysis = {
        "name": commodity.name,
        "current_price": commodity.current_price,
        "unit": commodity.unit,
    }

    # Supply/Demand Balance
    annual_deficit = commodity.annual_consumption - commodity.annual_production
    deficit_pct = (annual_deficit / commodity.annual_production) * 100

    analysis["supply_demand"] = {
        "annual_production": commodity.annual_production,
        "annual_consumption": commodity.annual_consumption,
        "annual_deficit": annual_deficit,
        "deficit_pct_of_production": deficit_pct,
        "market_balance": "DEFICIT" if annual_deficit > 0 else "SURPLUS",
        "years_of_stocks_at_current_deficit": (
            commodity.above_ground_stocks / annual_deficit if annual_deficit > 0 else float('inf')
        )
    }

    # Supply Concentration Risk (Herfindahl-like)
    concentration_scores = list(commodity.supply_concentration.values())
    hhi = sum(s**2 for s in concentration_scores) / 10000
    analysis["supply_risk"] = {
        "concentration_hhi": hhi,
        "risk_level": "HIGH" if hhi > 0.15 else "MODERATE" if hhi > 0.10 else "LOW",
        "top_producer": max(commodity.supply_concentration.items(), key=lambda x: x[1]),
        "lead_time_years": commodity.new_supply_lead_time_years
    }

    # Price vs Cost Analysis
    margin_over_avg_cost = (commodity.current_price - commodity.production_cost_avg) / commodity.production_cost_avg
    margin_over_marginal = (commodity.current_price - commodity.production_cost_marginal) / commodity.production_cost_marginal

    analysis["price_analysis"] = {
        "current_price": commodity.current_price,
        "avg_production_cost": commodity.production_cost_avg,
        "marginal_production_cost": commodity.production_cost_marginal,
        "margin_over_avg_cost_pct": margin_over_avg_cost * 100,
        "margin_over_marginal_pct": margin_over_marginal * 100,
        "incentive_price_for_new_supply": commodity.production_cost_marginal * 1.2,  # 20% margin
        "price_signal": "INCENTIVIZING NEW SUPPLY" if margin_over_marginal > 0.2 else "NOT INCENTIVIZING"
    }

    # Demand Elasticity Impact
    analysis["demand_elasticity"] = {
        "elasticity": commodity.demand_elasticity,
        "interpretation": (
            "EXTREMELY INELASTIC - price has little effect on demand" if commodity.demand_elasticity > -0.3
            else "INELASTIC - limited substitution" if commodity.demand_elasticity > -0.6
            else "MODERATE - some demand destruction at high prices"
        ),
        "implication": "Supply shortages will cause large price spikes" if commodity.demand_elasticity > -0.5 else "Some demand destruction will limit price spikes"
    }

    # Forward Projection
    years_forward = 5
    projected_demand = commodity.annual_consumption * (1 + commodity.demand_growth_rate/100) ** years_forward
    projected_supply = commodity.annual_production * (1 + commodity.production_growth_rate/100) ** years_forward
    future_deficit = projected_demand - projected_supply

    analysis["5_year_projection"] = {
        "projected_demand": projected_demand,
        "projected_supply": projected_supply,
        "projected_deficit": future_deficit,
        "deficit_growth": (future_deficit - annual_deficit) / abs(annual_deficit) * 100 if annual_deficit != 0 else 0,
        "outlook": "BULLISH" if future_deficit > annual_deficit else "NEUTRAL"
    }

    # Investment Thesis Score (1-10)
    score = 0
    if annual_deficit > 0:
        score += 2
    if deficit_pct > 10:
        score += 1
    if hhi > 0.15:
        score += 1
    if commodity.new_supply_lead_time_years > 10:
        score += 1
    if commodity.demand_elasticity > -0.5:
        score += 1
    if commodity.demand_growth_rate > 3:
        score += 1
    if margin_over_marginal < 0.3:  # Price not high enough to incentivize
        score += 1
    if future_deficit > annual_deficit:
        score += 2

    analysis["investment_thesis"] = {
        "score": score,
        "rating": "STRONG BUY" if score >= 8 else "BUY" if score >= 6 else "HOLD" if score >= 4 else "AVOID",
        "key_catalysts": commodity.catalyst_events[:3],
        "key_risks": commodity.known_supply_constraints[:3]
    }

    return analysis


def print_commodity_analysis(analysis: Dict):
    """Pretty print commodity analysis"""
    print(f"\n{'='*70}")
    print(f"SUPPLY/DEMAND ANALYSIS: {analysis['name']}")
    print(f"{'='*70}")

    sd = analysis['supply_demand']
    print(f"\n📊 SUPPLY/DEMAND BALANCE:")
    print(f"   Annual Production:  {sd['annual_production']:,.0f} {analysis['unit']}")
    print(f"   Annual Consumption: {sd['annual_consumption']:,.0f} {analysis['unit']}")
    print(f"   Annual Balance:     {sd['annual_deficit']:,.0f} {analysis['unit']} ({sd['market_balance']})")
    print(f"   Deficit % of Production: {sd['deficit_pct_of_production']:.1f}%")
    if sd['annual_deficit'] > 0:
        print(f"   Years of Stocks Remaining: {sd['years_of_stocks_at_current_deficit']:.1f} years")

    sr = analysis['supply_risk']
    print(f"\n⚠️  SUPPLY RISK:")
    print(f"   Concentration (HHI): {sr['concentration_hhi']:.3f} ({sr['risk_level']})")
    print(f"   Top Producer: {sr['top_producer'][0]} ({sr['top_producer'][1]}%)")
    print(f"   New Supply Lead Time: {sr['lead_time_years']} years")

    pa = analysis['price_analysis']
    print(f"\n💰 PRICE ANALYSIS:")
    print(f"   Current Price:      ${pa['current_price']:.2f}/{analysis['unit']}")
    print(f"   Avg Production Cost: ${pa['avg_production_cost']:.2f}/{analysis['unit']}")
    print(f"   Marginal Cost:      ${pa['marginal_production_cost']:.2f}/{analysis['unit']}")
    print(f"   Incentive Price:    ${pa['incentive_price_for_new_supply']:.2f}/{analysis['unit']}")
    print(f"   {pa['price_signal']}")

    de = analysis['demand_elasticity']
    print(f"\n📈 DEMAND CHARACTERISTICS:")
    print(f"   Elasticity: {de['elasticity']}")
    print(f"   {de['interpretation']}")

    fp = analysis['5_year_projection']
    print(f"\n🔮 5-YEAR PROJECTION:")
    print(f"   Projected Demand: {fp['projected_demand']:,.0f} {analysis['unit']}")
    print(f"   Projected Supply: {fp['projected_supply']:,.0f} {analysis['unit']}")
    print(f"   Projected Deficit: {fp['projected_deficit']:,.0f} {analysis['unit']}")
    print(f"   Outlook: {fp['outlook']}")

    it = analysis['investment_thesis']
    print(f"\n🎯 INVESTMENT THESIS:")
    print(f"   Score: {it['score']}/10 - {it['rating']}")
    print(f"   Key Catalysts:")
    for date, event in it['key_catalysts']:
        print(f"      [{date}] {event}")


# =============================================================================
# SECTION 3: BITCOIN FUNDAMENTAL VALUATION
# =============================================================================

@dataclass
class BitcoinValuationModel:
    """
    Framework for Bitcoin fundamental valuation

    Academic sources:
    - "Bitcoin Valuation" - Yale SOM (2019)
    - "An Investor's Take on Cryptoassets" - Harvard Business Review
    - "Modeling Bitcoin Value with Scarcity" - PlanB (Stock-to-Flow)
    - "Bitcoin Network Metrics" - Stanford Blockchain Research
    """

    # Fixed Supply Parameters (known with certainty)
    TOTAL_SUPPLY: int = 21_000_000
    CURRENT_SUPPLY: int = 19_600_000  # as of 2025
    LOST_COINS_ESTIMATE: int = 3_700_000  # ~20% permanently lost (Chainalysis)
    CIRCULATING_SUPPLY: int = 15_900_000  # Current - Lost

    # Halving Schedule (known with certainty)
    HALVINGS = [
        (2012, 50, 25),      # Block reward: 50 → 25
        (2016, 25, 12.5),    # 25 → 12.5
        (2020, 12.5, 6.25),  # 12.5 → 6.25
        (2024, 6.25, 3.125), # 6.25 → 3.125
        (2028, 3.125, 1.5625),
        (2032, 1.5625, 0.78125),
    ]

    # Stock-to-Flow (scarcity metric)
    CURRENT_ANNUAL_ISSUANCE: int = 164_250  # 3.125 BTC/block * 6 blocks/hr * 24 * 365
    STOCK_TO_FLOW: float = 19_600_000 / 164_250  # ~119 (higher than gold!)


def calculate_bitcoin_valuation() -> Dict:
    """
    Multiple valuation frameworks for Bitcoin

    The challenge: Bitcoin has no cash flows, so traditional DCF doesn't apply.
    We must use alternative frameworks.
    """

    valuation = {}

    # =========================================================================
    # MODEL 1: STOCK-TO-FLOW (Scarcity-Based)
    # =========================================================================
    # Based on PlanB's research: ln(market_cap) = 3.3 * ln(S2F) + constant
    # Gold S2F: ~62, Silver S2F: ~22, Bitcoin S2F: ~119 (post-2024 halving)

    current_supply = 19_600_000
    annual_issuance = 164_250
    s2f = current_supply / annual_issuance

    # S2F model price = e^(3.3 * ln(S2F) - 1.84) / supply * market_cap_coefficient
    # Simplified: price ≈ S2F^3.3 * coefficient
    s2f_price = (s2f ** 1.8) * 1000  # Calibrated coefficient

    valuation["stock_to_flow"] = {
        "model": "Stock-to-Flow (Scarcity)",
        "current_s2f": s2f,
        "gold_s2f": 62,
        "bitcoin_scarcity_vs_gold": f"Bitcoin is {s2f/62:.1f}x more scarce than gold",
        "model_price_usd": s2f_price,
        "methodology": "Higher scarcity → higher value. Bitcoin's S2F doubles every halving.",
        "criticism": "Assumes scarcity alone drives value. Ignores demand side."
    }

    # =========================================================================
    # MODEL 2: TOTAL ADDRESSABLE MARKET (TAM) APPROACH
    # =========================================================================
    # What markets could Bitcoin capture a share of?

    tam_analysis = {
        "gold_market": {
            "total_value_usd": 13_000_000_000_000,  # $13T
            "btc_capture_rate_conservative": 0.05,  # 5%
            "btc_capture_rate_bull": 0.25,  # 25%
        },
        "store_of_value": {
            "total_value_usd": 10_000_000_000_000,  # $10T (part of gold + other)
            "btc_capture_rate_conservative": 0.10,
            "btc_capture_rate_bull": 0.30,
        },
        "offshore_banking": {
            "total_value_usd": 8_000_000_000_000,  # $8T
            "btc_capture_rate_conservative": 0.05,
            "btc_capture_rate_bull": 0.15,
        },
        "remittances": {
            "total_value_usd": 700_000_000_000,  # $700B/year
            "btc_capture_rate_conservative": 0.10,
            "btc_capture_rate_bull": 0.30,
        },
        "treasury_reserves": {
            "total_value_usd": 1_000_000_000_000,  # $1T corporate treasuries
            "btc_capture_rate_conservative": 0.05,
            "btc_capture_rate_bull": 0.20,
        }
    }

    circulating_supply = 15_900_000  # Adjusted for lost coins

    conservative_tam = sum(
        market["total_value_usd"] * market["btc_capture_rate_conservative"]
        for market in tam_analysis.values()
    )
    bull_tam = sum(
        market["total_value_usd"] * market["btc_capture_rate_bull"]
        for market in tam_analysis.values()
    )

    conservative_price = conservative_tam / circulating_supply
    bull_price = bull_tam / circulating_supply

    valuation["tam_approach"] = {
        "model": "Total Addressable Market",
        "conservative_tam_usd": conservative_tam,
        "bull_tam_usd": bull_tam,
        "circulating_supply": circulating_supply,
        "conservative_price_usd": conservative_price,
        "bull_price_usd": bull_price,
        "markets_analyzed": list(tam_analysis.keys()),
        "methodology": "Sum of market captures / circulating supply",
        "criticism": "Capture rates are speculative. Ignores regulatory risk."
    }

    # =========================================================================
    # MODEL 3: NETWORK VALUE TO TRANSACTIONS (NVT) - Metcalfe's Law
    # =========================================================================
    # Like P/E ratio for Bitcoin. NVT = Market Cap / Daily Transaction Volume

    current_daily_tx_volume = 10_000_000_000  # ~$10B/day on-chain
    annual_tx_volume = current_daily_tx_volume * 365

    # Historical fair NVT range: 50-100
    fair_nvt_low = 50
    fair_nvt_high = 100

    # Market cap = NVT * Daily Volume
    fair_mcap_low = fair_nvt_low * current_daily_tx_volume * 365 / 52  # Weekly adjusted
    fair_mcap_high = fair_nvt_high * current_daily_tx_volume * 365 / 52

    nvt_price_low = fair_mcap_low / circulating_supply
    nvt_price_high = fair_mcap_high / circulating_supply

    valuation["nvt_ratio"] = {
        "model": "Network Value to Transactions (NVT)",
        "current_daily_volume": current_daily_tx_volume,
        "fair_nvt_range": f"{fair_nvt_low}-{fair_nvt_high}",
        "fair_price_range_usd": f"${nvt_price_low:,.0f} - ${nvt_price_high:,.0f}",
        "methodology": "Market cap should be proportional to network transaction value",
        "criticism": "Doesn't account for off-chain (Lightning, exchanges) activity"
    }

    # =========================================================================
    # MODEL 4: PRODUCTION COST FLOOR (Marginal Cost of Mining)
    # =========================================================================
    # Miners won't sell below production cost for long

    electricity_cost_per_btc = 25_000  # Average global
    hardware_amortization = 10_000
    operations_costs = 5_000

    production_cost = electricity_cost_per_btc + hardware_amortization + operations_costs

    # Historical: BTC trades at 2-5x production cost
    floor_multiple_bear = 1.5
    floor_multiple_fair = 2.5
    floor_multiple_bull = 4.0

    valuation["production_cost"] = {
        "model": "Production Cost Floor",
        "mining_cost_per_btc": production_cost,
        "bear_price": production_cost * floor_multiple_bear,
        "fair_price": production_cost * floor_multiple_fair,
        "bull_price": production_cost * floor_multiple_bull,
        "methodology": "Price should stay above miner production costs",
        "criticism": "Production cost adjusts to price (more efficient miners enter/exit)"
    }

    # =========================================================================
    # MODEL 5: METCALFE'S LAW (Network Effect)
    # =========================================================================
    # Value ∝ n^2 where n = number of users

    current_addresses = 50_000_000  # Unique addresses with balance

    # Calibrate: current price ~$100k, 50M addresses
    # Price = k * n^1.5 (modified Metcalfe's)
    k_coefficient = 100_000 / (50_000_000 ** 1.5) * 1_000_000_000

    # Project forward
    addresses_2030 = 150_000_000  # 3x growth estimate
    addresses_2035 = 300_000_000  # 6x growth estimate

    price_2030 = k_coefficient * (addresses_2030 ** 1.5) / 1_000_000_000
    price_2035 = k_coefficient * (addresses_2035 ** 1.5) / 1_000_000_000

    valuation["metcalfes_law"] = {
        "model": "Metcalfe's Law (Network Effect)",
        "current_addresses": current_addresses,
        "projected_addresses_2030": addresses_2030,
        "projected_addresses_2035": addresses_2035,
        "projected_price_2030": price_2030,
        "projected_price_2035": price_2035,
        "methodology": "Value grows with square of network participants",
        "criticism": "Address count != users. Many addresses per person."
    }

    # =========================================================================
    # SYNTHESIS: Weighted Average Fair Value
    # =========================================================================

    # Weight models by credibility
    weights = {
        "stock_to_flow": 0.15,
        "tam_conservative": 0.25,
        "tam_bull": 0.15,
        "nvt_mid": 0.15,
        "production_cost_fair": 0.20,
        "metcalfe_current": 0.10
    }

    weighted_price = (
        s2f_price * weights["stock_to_flow"] +
        conservative_price * weights["tam_conservative"] +
        bull_price * weights["tam_bull"] +
        ((nvt_price_low + nvt_price_high) / 2) * weights["nvt_mid"] +
        (production_cost * 2.5) * weights["production_cost_fair"] +
        100_000 * weights["metcalfe_current"]  # Current implied
    )

    valuation["synthesis"] = {
        "weighted_fair_value_usd": weighted_price,
        "weights_used": weights,
        "range_low_usd": min(conservative_price, production_cost * 1.5, nvt_price_low),
        "range_high_usd": max(bull_price, s2f_price, nvt_price_high),
        "methodology": "Weighted average of all models",
        "confidence": "MODERATE - Multiple models, significant uncertainty"
    }

    # =========================================================================
    # DEMAND DRIVERS (The Key Question)
    # =========================================================================

    valuation["demand_analysis"] = {
        "current_demand_drivers": [
            {
                "driver": "Store of Value / Digital Gold",
                "strength": "HIGH",
                "evidence": "ETF inflows ($30B+), institutional adoption",
                "growth_trajectory": "INCREASING"
            },
            {
                "driver": "Inflation Hedge",
                "strength": "MODERATE",
                "evidence": "Correlation with real yields mixed",
                "growth_trajectory": "STABLE"
            },
            {
                "driver": "Speculation",
                "strength": "HIGH",
                "evidence": "Retail trading volume, derivatives market",
                "growth_trajectory": "CYCLICAL"
            },
            {
                "driver": "Payments / Remittances",
                "strength": "LOW",
                "evidence": "Lightning adoption slow, volatility deters use",
                "growth_trajectory": "SLOW GROWTH"
            },
            {
                "driver": "Corporate Treasury",
                "strength": "MODERATE",
                "evidence": "MicroStrategy, Tesla, etc.",
                "growth_trajectory": "INCREASING"
            },
            {
                "driver": "Sovereign Reserves",
                "strength": "LOW (but growing)",
                "evidence": "El Salvador, proposed US strategic reserve",
                "growth_trajectory": "POTENTIALLY HIGH"
            }
        ],
        "key_insight": """
        Unlike commodities (silver, uranium, copper), Bitcoin's demand is almost
        entirely SPECULATIVE and STORE-OF-VALUE based. There is minimal industrial
        or consumption demand. This makes valuation more uncertain.

        The 'true demand' question for Bitcoin is: How much wealth will humans
        want to store in a digitally scarce, decentralized asset?

        This is fundamentally a question about:
        1. Trust in traditional financial systems
        2. Inflation expectations
        3. Regulatory acceptance
        4. Network effect momentum

        Unlike copper (where EV mandates create calculable demand) or uranium
        (where reactor counts create calculable demand), Bitcoin demand is a
        social/psychological phenomenon.
        """
    }

    return valuation


def print_bitcoin_valuation(valuation: Dict):
    """Pretty print Bitcoin valuation analysis"""
    print("\n" + "="*70)
    print("BITCOIN FUNDAMENTAL VALUATION ANALYSIS")
    print("="*70)

    for model_name, model in valuation.items():
        if model_name in ["stock_to_flow", "tam_approach", "nvt_ratio",
                          "production_cost", "metcalfes_law"]:
            print(f"\n📊 {model['model'].upper()}")
            for key, value in model.items():
                if key not in ["model", "methodology", "criticism"]:
                    print(f"   {key}: {value}")
            print(f"   Methodology: {model['methodology']}")
            print(f"   ⚠️  Criticism: {model['criticism']}")

    syn = valuation["synthesis"]
    print(f"\n{'='*70}")
    print("🎯 SYNTHESIS")
    print(f"{'='*70}")
    print(f"   Weighted Fair Value: ${syn['weighted_fair_value_usd']:,.0f}")
    print(f"   Range: ${syn['range_low_usd']:,.0f} - ${syn['range_high_usd']:,.0f}")
    print(f"   Confidence: {syn['confidence']}")

    print(f"\n{'='*70}")
    print("📈 DEMAND ANALYSIS")
    print(f"{'='*70}")
    for driver in valuation["demand_analysis"]["current_demand_drivers"]:
        print(f"\n   {driver['driver']}")
        print(f"      Strength: {driver['strength']}")
        print(f"      Evidence: {driver['evidence']}")
        print(f"      Trajectory: {driver['growth_trajectory']}")

    print(f"\n💡 KEY INSIGHT:")
    print(valuation["demand_analysis"]["key_insight"])


# =============================================================================
# SECTION 4: COMPARATIVE ANALYSIS
# =============================================================================

def compare_commodities_vs_bitcoin():
    """
    Compare the investment calculability of commodities vs Bitcoin
    """
    print("\n" + "="*70)
    print("COMMODITIES vs BITCOIN: CALCULABILITY COMPARISON")
    print("="*70)

    comparison = """
    ┌─────────────────┬───────────────────────────────────────┬────────────────────────────────────┐
    │ Factor          │ COMMODITIES (Cu, Ag, U)               │ BITCOIN                            │
    ├─────────────────┼───────────────────────────────────────┼────────────────────────────────────┤
    │ Supply          │ ✅ Calculable                          │ ✅ Perfectly Known (21M cap)        │
    │ Predictability  │ Geology, mine permits, lead times     │ Fixed issuance schedule            │
    │                 │ are PUBLIC information                │                                    │
    ├─────────────────┼───────────────────────────────────────┼────────────────────────────────────┤
    │ Demand          │ ✅ Calculable                          │ ❌ Speculative                      │
    │ Predictability  │ Industrial use, committed investments │ Depends on adoption, sentiment     │
    │                 │ (EV factories, reactors, solar farms) │ No "consumption" demand            │
    ├─────────────────┼───────────────────────────────────────┼────────────────────────────────────┤
    │ Price           │ ✅ Supply/Demand driven                │ ⚠️  Narrative/Sentiment driven     │
    │ Discovery       │ Industrial buyers MUST buy            │ Nobody MUST buy Bitcoin            │
    │                 │ (can't make EVs without copper)       │ (pure store of value choice)       │
    ├─────────────────┼───────────────────────────────────────┼────────────────────────────────────┤
    │ Valuation       │ ✅ DCF on miners, S/D models           │ ⚠️  Multiple competing models      │
    │ Framework       │ Well-established methodologies        │ No consensus on "right" model      │
    ├─────────────────┼───────────────────────────────────────┼────────────────────────────────────┤
    │ Substitutes     │ Limited (can't substitute copper)     │ Unlimited (any store of value)     │
    │                 │                                       │ Gold, real estate, stocks...       │
    ├─────────────────┼───────────────────────────────────────┼────────────────────────────────────┤
    │ Investment      │ 8-9/10                                │ 4-5/10                             │
    │ Calculability   │ High predictability if you do work    │ More art than science              │
    └─────────────────┴───────────────────────────────────────┴────────────────────────────────────┘

    CONCLUSION:

    Your intuition is correct: Commodities (especially industrial metals like copper,
    silver, uranium) offer more CALCULABLE investment theses because:

    1. DEMAND IS COMMITTED: Governments have mandated EV adoption, reactor builds,
       renewable installations. These are not speculative - contracts are signed.

    2. SUPPLY IS CONSTRAINED: Geology doesn't care about price. New mines take
       10-20 years. You can calculate when supply gaps will occur.

    3. NO SUBSTITUTES: You cannot make an EV without copper. You cannot run a
       reactor without uranium. Industrial users MUST buy.

    4. INFORMATION IS PUBLIC: Reactor construction schedules, EV production plans,
       mine depletion rates are all published data.

    Bitcoin, while having perfect supply predictability, has UNKNOWN demand because:
    - Demand is psychological/social, not industrial
    - Substitutes exist (any store of value)
    - No one MUST buy Bitcoin
    - Valuation frameworks are contested

    This doesn't make Bitcoin a bad investment - it just means the thesis is
    fundamentally different. Commodities = calculable S/D imbalance.
    Bitcoin = bet on monetary network effect and store of value adoption.
    """
    print(comparison)


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Run complete supply/demand analysis"""

    print("\n" + "="*70)
    print("SUPPLY/DEMAND ANALYSIS FRAMEWORK")
    print("Buffett/Munger: 'In the short run, the market is a voting machine.")
    print("In the long run, it is a weighing machine.'")
    print("="*70)

    # Historical case studies
    print("\n\n" + "="*70)
    print("PART 1: HISTORICAL CASE STUDIES")
    print("="*70)
    analyze_all_case_studies()

    # Commodity analysis
    print("\n\n" + "="*70)
    print("PART 2: COMMODITY FUNDAMENTAL ANALYSIS")
    print("="*70)

    for commodity in [SILVER_FUNDAMENTALS, URANIUM_FUNDAMENTALS, COPPER_FUNDAMENTALS]:
        analysis = analyze_commodity_fundamentals(commodity)
        print_commodity_analysis(analysis)

    # Bitcoin valuation
    print("\n\n" + "="*70)
    print("PART 3: BITCOIN VALUATION")
    print("="*70)
    btc_valuation = calculate_bitcoin_valuation()
    print_bitcoin_valuation(btc_valuation)

    # Comparison
    print("\n\n" + "="*70)
    print("PART 4: COMPARATIVE ANALYSIS")
    print("="*70)
    compare_commodities_vs_bitcoin()

    # Summary
    print("\n\n" + "="*70)
    print("EXECUTIVE SUMMARY")
    print("="*70)

    summary = """
    KEY TAKEAWAYS:

    1. COMMODITIES (Silver, Uranium, Copper) offer CALCULABLE investment theses:
       - Supply constraints are geological and public
       - Demand is committed through infrastructure investments
       - Price must rise to incentivize new production
       - 5-year deficits are calculable with reasonable confidence

    2. BITCOIN offers a DIFFERENT investment thesis:
       - Supply is perfectly known (advantage)
       - Demand is speculative/psychological (disadvantage for calculation)
       - Valuation requires multiple models with wide ranges
       - Thesis is about monetary adoption, not industrial necessity

    3. HISTORICAL PATTERNS show supply/demand imbalances are PREDICTABLE:
       - The 2000s commodity supercycle (China) was highly predictable
       - Current energy transition demand (Cu, Ag, U) is similarly predictable
       - Information is public: reactor orders, EV mandates, mine permits

    4. ACTIONABLE INSIGHT:
       - For CALCULABLE returns: Focus on commodities with known supply
         constraints and committed demand (copper, uranium, silver for solar)
       - For ASYMMETRIC bets: Bitcoin offers high upside if monetary
         adoption thesis plays out, but less calculable probability

    RECOMMENDED NEXT STEPS:
    1. Track committed demand projects (reactor orders, EV factory announcements)
    2. Monitor supply disruptions (mine closures, permit delays)
    3. Watch inventory levels (LME, COMEX warehouse stocks)
    4. For Bitcoin: Track adoption metrics (addresses, ETF flows, sovereign buys)
    """
    print(summary)


if __name__ == "__main__":
    main()
