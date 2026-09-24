#!/usr/bin/env python3
"""Build the Field guide reference section for Heavy Reading.

Plain-language explainers on how the oil sands plumbing actually works.
Not numbers, not S&D framing: the institutional knowledge that makes the
numbers legible. Written for a new hire on a WCSB desk.

Writes:
  site/fieldguide/index.html
  site/fieldguide/<slug>.html   (11 explainers)

Then rewires the sitenav block on every existing page (except the
dashboard, whose nav is hardcoded in its own builder) to include the new
"Field guide" item. shared.py carries the new NAV_ITEMS/_TARGETS entries,
so future full rebuilds pick it up automatically.

Run:  python site/build_fieldguide.py
Idempotent. Touches no model numbers, no dashboard data, no forecast logic.
"""
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
BASE = SITE.parent

sys.path.insert(0, str(SITE))
import shared as S  # noqa: E402

WRITTEN = "September 23, 2026"
FG = SITE / "fieldguide"


def P(*paras):
    return "".join(f"<p>{p}</p>" for p in paras)


def UL(*items):
    return "<ul class=\"ev\">" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def why(text):
    return (f'<div class="exec"><h2>Why it matters</h2><p>{text}</p></div>')


def sources_list(srcs):
    items = []
    for pub, doc, url in srcs:
        if url:
            items.append(f"{S.esc(pub)}, {S.esc(doc)} "
                         f'(<a href="{S.esc(url)}">{S.esc(url)}</a>)')
        else:
            items.append(f"{S.esc(pub)}, {S.esc(doc)} "
                         "(URL not recorded)")
    return "<h2>Sources</h2>" + UL(*items)


EXPLAINERS = [
    dict(
        slug="scotford-chain",
        title="The Scotford chain",
        deck=("Muskeg River and Jackpine mines, the Corridor pipeline, and a "
              "Shell-operated upgrader outside Edmonton. How CNRL's mined "
              "bitumen becomes synthetic crude."),
        source_line="Company disclosures (CNRL, Shell) via newswire; AER ST39",
        body=[
            ("What it is", P(
                "The Scotford chain is the Athabasca Oil Sands Project's path "
                "from mine to synthetic crude. Bitumen comes out of the Muskeg "
                "River and Jackpine mines north of Fort McMurray, travels south "
                "by pipeline as diluted bitumen, and gets upgraded into "
                "synthetic crude at the Scotford Upgrader near Fort "
                "Saskatchewan, just northeast of Edmonton. It is one of two "
                "upgrader systems tied to Canadian Natural Resources. The other "
                "is Horizon, which is fully integrated on a single site.")),
            ("How it works, physically", P(
                "The mines use paraffinic froth treatment, which produces "
                "bitumen clean enough to meet pipeline spec. That bitumen is "
                "blended with diluent and shipped down the Corridor pipeline "
                "to Scotford; the diluent comes back north in a reverse loop "
                "on the same system. At Scotford the upgrader runs LC-Fining, "
                "a hydrogen-addition process that cracks the heavy residue "
                "into lighter products. Because it adds hydrogen rather than "
                "rejecting carbon as coke, the plant puts out slightly more "
                "liquid than it takes in as bitumen. The main products are "
                "Premium Albian Synthetic (a light sweet SCO), vacuum gas oil, "
                "and Albian Heavy Synthetic. A large share of the output feeds "
                "the Shell Scotford refinery next door; the rest goes to "
                "Sarnia and the open market.")),
            ("Who owns and operates it", P(
                "This is the confusing part, and it changed twice. In 2017 "
                "CNRL bought Shell's 60 percent of the Athabasca Oil Sands "
                "Project and took over operating the mines. Shell stayed on "
                "as operator of the upgrader and the Quest carbon capture "
                "unit. Then in a 2025 asset swap, CNRL traded 10 percent of "
                "the upgrader and Quest to Shell in exchange for Shell's "
                "remaining 10 percent of the mines. The deal closed late in "
                "2025. The result: the mines are now 100 percent CNRL, while "
                "the upgrader is owned 60 percent CNRL, 20 percent Shell, and "
                "20 percent Chevron. Shell still operates the upgrader.")),
            ("Key numbers", UL(
                "Rated SCO capacity around 255 kb/d, after a 100 kb/d "
                "expansion in 2011.",
                "Roughly 280 kb/d of bitumen in.",
                "Product split disclosed at the 2017 acquisition: about "
                "150 kb/d Premium Albian Synthetic, 60 kb/d vacuum gas oil, "
                "79 kb/d Albian Heavy Synthetic, plus a small off-gas stream.",
                "The Quest carbon capture unit attached to the upgrader "
                "captures about 1.1 million tonnes of CO2 per year.")),
        ],
        why=("CNRL digs up bitumen it fully owns, then feeds it to an upgrader "
             "it only majority-owns and does not operate. The SCO that comes "
             "out is a joint-venture stream, not CNRL SCO. And unlike the "
             "Suncor-Syncrude pair, there is no interconnect to lean on: a "
             "Scotford turnaround means the Albian mines dial back directly. "
             "Compare Horizon, where the mine and upgrader sit on one site "
             "and both are 100 percent CNRL."),
        sources=[
            ("Canadian Natural Resources", "Acquisition of working interest in "
             "the Athabasca Oil Sands Project, news release (2017-03-09)",
             "https://boereport.com/2017/03/09/canadian-natural-resources-limited-announces-the-acquisition-of-working-interest-in-the-athabasca-oil-sands-project-and-other-oil-sands-assets/amp/"),
            ("The Canadian Press via BOE Report", "Canadian Natural raises "
             "production outlook after taking full control of oilsands mine "
             "(2025-11-03)",
             "https://boereport.com/2025/11/03/canadian-natural-raises-production-outlook-after-taking-full-control-of-oilsands-mine/"),
            ("Oil Sands Magazine", "Scotford Upgrader project page",
             "https://www.oilsandsmagazine.com/projects/shell-scotford-upgrader"),
        ],
    ),
    dict(
        slug="sturgeon-refinery",
        title="The Sturgeon refinery",
        deck=("The government-backed bitumen refinery northeast of Edmonton. "
              "Fifty thousand barrels a day of bitumen that never sees an "
              "export pipe."),
        source_line="Government of Alberta; U of C School of Public Policy; APMC",
        body=[
            ("What it is", P(
                "The North West Redwater Sturgeon Refinery is the plant people "
                "mean when they say 'the government refinery.' It sits "
                "northeast of Edmonton and it is the first refinery built in "
                "Canada since 1984, and the first anywhere in the country "
                "designed to take bitumen all the way to finished products. "
                "Most oil sands plants either upgrade bitumen to synthetic "
                "crude (which still needs refining) or dilute it for sale. "
                "Sturgeon does the whole job: bitumen in, diesel out.")),
            ("How it works, physically", P(
                "Phase 1 takes 50,000 barrels a day of bitumen blended with "
                "29,000 barrels a day of diluent. Out the other end come "
                "roughly 40,000 barrels a day of low-sulphur diesel, about "
                "28,000 barrels a day of recovered diluent, and 13,000 "
                "barrels a day of lighter products. The diluent recovery "
                "matters: of the 29 kb/d that goes in, 28 comes back, so the "
                "plant's net draw on the diluent pool is only about 1 kb/d. "
                "The refinery gasifies the heaviest residue to make its own "
                "hydrogen, and it was built with carbon capture on the "
                "hydrogen unit.")),
            ("Who owns it and who pays", P(
                "The commercial structure is a tolling deal. The Alberta "
                "Petroleum Marketing Commission, the province's oil marketer, "
                "is the 75 percent toll payer; CNRL covers the other 25 "
                "percent. Under tolling, the two parties keep ownership of "
                "the bitumen straight through the refining process and pay "
                "the plant a fee for the service. The province's auditor "
                "general later described the deal as high benefit and high "
                "risk: about $26 billion in toll payments over thirty years, "
                "with the province carrying most of the risk of a 75 percent "
                "payer while holding a minority vote. In a 2021 restructuring "
                "the province took a 50 percent ownership stake from North "
                "West Refining, CNRL took operational leadership, and the "
                "processing agreement was extended to 2058. The province says "
                "the rework improved its net present value by about $2 "
                "billion.")),
            ("Key numbers", UL(
                "50 kb/d bitumen plus 29 kb/d diluent in; about 40 diesel, "
                "28 diluent recovered, and 13 light products out.",
                "Thirty-year tolling agreements covering 100 percent of "
                "Phase 1 feedstock.",
                "Two further 50 kb/d phases were planned, to 150 kb/d total. "
                "They were never built.")),
        ],
        why=("Sturgeon is 50 kb/d of baseload domestic bitumen demand. Those "
             "barrels never touch an export pipeline, which tightens the "
             "exportable surplus by exactly that amount. It is also a "
             "demand-side maintenance risk in reverse: if Sturgeon ever takes "
             "a major turnaround, 50 kb/d of bitumen suddenly needs a pipe to "
             "market."),
        sources=[
            ("Government of Alberta", "Getting taxpayers a better deal on the "
             "Sturgeon Refinery, news release",
             "https://www.alberta.ca/release.cfm?xID=79503ADBD9811-E4F1-1DAB-A5BA42F70D2063D6"),
            ("U of Calgary School of Public Policy (Brian Livingston)",
             "The North West Redwater Sturgeon Refinery: What are the numbers "
             "for Alberta's investment?",
             "https://www.policyschool.ca/wp-content/uploads/2018/06/NWR-Strugeon-Refinery-Livingston-FINAL-VERSION1.pdf"),
            ("Wikipedia", "Sturgeon Refinery",
             "https://en.wikipedia.org/wiki/Sturgeon_Refinery"),
        ],
    ),
    dict(
        slug="upgrader-interconnects",
        title="The upgrader interconnects",
        deck=("The bitumen lines between Suncor and Syncrude, and the "
              "unplanned-outage playbook they make possible."),
        source_line="Heavy Reading research: company disclosures and AER ST39/ST53, verified 2026-09-23",
        body=[
            ("What they are", P(
                "Two bi-directional pipelines connect the Suncor and Syncrude "
                "complexes, in service since around 2020/21. They move "
                "bitumen, not synthetic crude: raw mined bitumen can flow "
                "either way between Syncrude's Mildred Lake and Aurora mines "
                "and Suncor's Base upgrader, and the reverse. They are "
                "generally described as Suncor-Syncrude interconnects; the "
                "companies have not published a separate ownership split "
                "for the lines themselves.")),
            ("What happened in Q1 2026", P(
                "The documented case is the Syncrude coker outage in the "
                "first quarter of 2026. With Syncrude's upgrader constrained, "
                "about 16.4 kb/d of Syncrude bitumen flowed to Suncor's Base "
                "upgrader, and about 66.9 kb/d of Fort Hills bitumen was "
                "redirected to Base as well. Base ran at 108 percent "
                "utilization. The telling detail: Suncor's non-upgraded "
                "bitumen, the barrels sold as dilbit, ROSE during the outage, "
                "to 279.5 kb/d, which the company attributed primarily to "
                "decreased upgrader availability.")),
            ("The unplanned outage playbook", P(
                "When an upgrader trips unexpectedly at an interconnected "
                "site, three things happen at once. First, the mine dials "
                "back, but only partially: in Suncor/Syncrude upgrader-only "
                "outages the mine typically gives up 30 to 60 percent of the "
                "synthetic crude oil (SCO) rate, not the full amount. Second, "
                "the balance of the bitumen redirects through the interconnect "
                "to the other site's upgrader, which shows up as a partial "
                "SCO offset. Third, flexible barrels tilt toward dilbit: "
                "Firebag and Fort Hills can swing between upgrader feed and "
                "dilbit sales, and they tilt to dilbit when upgrading capacity "
                "is short. The net effect on marketable dilbit is ambiguous "
                "every time, which is exactly why the grade layer exists.")),
            ("Planned turnarounds are different", P(
                "None of the above applies when the outage is planned. A "
                "turnaround is scheduled months ahead, and the mine plan is "
                "set to match reduced upgrader demand, so no surplus bitumen "
                "is left looking for a relief valve and no redirect is "
                "assumed. The interconnect's economic purpose runs the other "
                "way: keeping a hungry upgrader fed when the mine stumbles, "
                "not moving surplus during a deliberate outage. The Q1 2026 "
                "precedent was an unplanned outage, where the mine could not "
                "react in time; it does not transfer to planned events. The "
                "applied example is the Syncrude Coker 8-2 turnaround ruling "
                "(2026-09-24): September 2026 SCO impact -77.0 kb/d at the "
                "Syncrude upgrader, heavy-market impact zero, no interconnect "
                "redirect.")),
            ("Where this does not apply", P(
                "Horizon and Scotford have no documented third-party "
                "interconnects. When their upgraders go down, the mines dial "
                "back in lockstep: Horizon turnarounds typically cut both "
                "lines 45 to 55 percent. Across 11 documented integrated-site "
                "events from 2022 to 2026, the mine dropped alongside the "
                "upgrader every single time. There is no counterexample on "
                "record.")),
        ],
        why=("Dilbit supply can RISE during an unplanned upgrader outage. Anyone "
             "modeling an unplanned outage as a straight subtraction of SCO from supply "
             "is missing the redirect and the dilbit tilt, and will get the "
             "heavy barrel wrong."),
        sources=[
            ("Heavy Reading research note",
             "Bitumen flexibility study: 11 documented integrated-site events "
             "2022-2026, verified 2026-09-23 from company disclosures and "
             "AER ST39/ST53",
             None),
            ("Suncor Energy", "Q1 2026 disclosures on Syncrude coker outage "
             "bitumen flows (via company reporting)",
             None),
        ],
    ),
    dict(
        slug="nft-vs-pft",
        title="NFT vs PFT bitumen",
        deck=("Why some mined bitumen has to go through an upgrader, and some "
              "can go straight to a pipeline."),
        source_line="Oil Sands Magazine technical reference; Heavy Reading research",
        body=[
            ("What froth treatment does", P(
                "Mined oil sand goes through hot-water extraction, which "
                "leaves a froth of bitumen mixed with water and fine clay "
                "solids. Froth treatment cleans that up by diluting the froth "
                "with a light hydrocarbon and separating the three phases. "
                "The choice of hydrocarbon decides what comes out the other "
                "end, and that choice splits the industry in two.")),
            ("Naphthenic (NFT)", P(
                "The original process, used for 30-plus years at Syncrude and "
                "Suncor. It dilutes the froth with naphtha, a heavier, more "
                "viscous hydrocarbon. No asphaltenes precipitate, so the "
                "bitumen keeps its full asphaltene load (17 to 18 percent) "
                "and the product still carries about 2 percent water plus "
                "solids. That fails the pipeline spec for basic sediment and "
                "water, which sits below 0.5 percent. NFT bitumen is therefore "
                "upgrader-locked: it has to go through a coker or "
                "hydrocracker next door before it can be sold. NFT plants: "
                "Suncor Base (Suncor operates), Syncrude Mildred Lake "
                "(Syncrude Canada operates), and CNRL Horizon (CNRL "
                "operates).")),
            ("Paraffinic (PFT)", P(
                "First commercialized by Albian Sands (Shell) in 2002. It "
                "uses a light paraffinic solvent, typically pentane or "
                "hexane. About half the asphaltenes precipitate out, and as "
                "they drop out they drag the trapped water and fine solids "
                "with them. The product is 99.9 percent bitumen with less "
                "than 0.1 percent water plus solids, comfortably inside "
                "pipeline spec. It can be diluted and sold directly as dilbit "
                "to a high-conversion refinery, no upgrader needed. The "
                "trade: rejecting the asphaltenes costs 5 to 10 percent of "
                "bitumen recovery versus NFT. PFT plants: Muskeg River and "
                "Jackpine (CNRL operates), Kearl (Imperial operates), and "
                "Fort Hills (Suncor operates).")),
            ("What \"paraffinic\" means", P(
                "Paraffins are straight-chain alkanes: pentane and hexane, "
                "the light stuff at the top of the barrel. They are thin, "
                "low-viscosity solvents. When mixed into bitumen froth, they "
                "make the heaviest, most polar molecules in the bitumen, the "
                "asphaltenes, fall out of solution as solids. Those falling "
                "solids act like a sweep, binding the water droplets and clay "
                "fines that gravity separation alone cannot remove. That is "
                "the whole trick: precipitation as purification, paid for "
                "with a few percent of yield.")),
            ("The in-between cases", P(
                "SAGD bitumen is not froth-treated at all; it comes up as an "
                "oil-water emulsion that is separated at the plant, and it "
                "flows both ways. About half of Firebag's output feeds "
                "Suncor's Base upgrader and the rest sells as dilbit; Long "
                "Lake went fully to dilbit after its upgrader idled in 2016. "
                "Kearl and Fort Hills sell their PFT bitumen directly as "
                "named dilbit streams: KDB (Kearl Lake Dilbit) and FRB (Fort "
                "Hills Dilbit).")),
        ],
        why=("Froth treatment decides a mine's commercial destiny. NFT "
             "barrels must be upgraded on site, so an upgrader outage strands "
             "them. PFT barrels are pipeline-ready, so they keep flowing as "
             "dilbit no matter what the upgrader is doing."),
        sources=[
            ("Oil Sands Magazine", "Froth Treatment Explained (technical "
             "reference)",
             "https://www.oilsandsmagazine.com/technical/mining/froth-treatment"),
            ("Oil Sands Magazine", "Paraffinic Froth Treatment (technical "
             "reference)",
             "https://www.oilsandsmagazine.com/technical/mining/froth-treatment/paraffinic"),
        ],
    ),
    dict(
        slug="diluent-101",
        title="Diluent 101",
        deck=("The light oil that makes bitumen move, and the 30 percent of "
              "every dilbit barrel you are really buying."),
        source_line="RBN Energy; Enbridge shipper documents",
        body=[
            ("What it is", P(
                "Diluent is light hydrocarbon liquid, mostly natural-gas "
                "condensate and natural gasoline (pentanes plus), blended "
                "into bitumen so it meets pipeline density and viscosity "
                "specs. The standard spec at Edmonton is known as CRW "
                "condensate. Producers also use butane and even synthetic "
                "crude as blendstock depending on price and availability.")),
            ("Why it is 30 percent", P(
                "Raw bitumen is around 8 API: at room temperature it barely "
                "flows. A pipeline needs something in the low-20s API with "
                "capped viscosity. The industry-standard answer is dilbit: "
                "roughly 70 percent bitumen and 30 percent diluent. The ratio "
                "moves a bit with the season and the exact spec, but 30 "
                "percent is the number the whole system is built around. For "
                "every three barrels of bitumen moved, close to one barrel "
                "of diluent has to be sourced, shipped north, blended, "
                "shipped south, and then mostly recovered at the refinery.")),
            ("Where it comes from", P(
                "Edmonton is the trading and delivery hub. Supply comes from "
                "Alberta NGL fractionation (Montney and Duvernay condensate), "
                "from US imports, and from refinery recovery. Canada has "
                "never produced enough condensate domestically to cover oil "
                "sands demand, so imports from the US are a structural "
                "feature of the trade, not a temporary fix. Dedicated return "
                "loops move diluent back north: the Corridor system runs "
                "diluted bitumen south and diluent north on the same "
                "corridor, and plants like Sturgeon recover about 28 of the "
                "29 kb/d they take in.")),
            ("Who handles it", P(
                "Nobody owns diluent as a system. Producers buy it, midstream "
                "companies move it, and Edmonton is where it trades. "
                "Enbridge sets the quality specs every shipper must meet. "
                "The clearest dedicated asset is the Corridor system, which "
                "runs diluent back north to the Albian mines on a reverse "
                "loop.")),
            ("Key numbers", UL(
                "Dilbit: about 70/30 bitumen to diluent, by volume.",
                "Diluent demand grows with bitumen production; older RBN work "
                "had it rising from 380 kb/d in 2014 toward 685 kb/d by "
                "2019, and SAGD growth keeps pushing it up.",
                "Net diluent draw at a recovering plant is small (Sturgeon: "
                "about 1 kb/d net on 29 in), but the gross logistics are not.")),
        ],
        why=("Thirty percent of every \"bitumen\" pipeline barrel is not "
             "bitumen. Diluent is a cost on every dilbit barrel, a logistics "
             "system of its own, and a second market that can squeeze "
             "independently: when condensate runs tight, the heavy barrel "
             "feels it."),
        sources=[
            ("RBN Energy", "Parallel Lines: The Diluent Trail Across Canada, "
             "Part 9 (Economics)",
             "https://rbnenergy.com/daily-posts/blog/parallel-lines-diluent-trail-across-canada-part-9-economics"),
            ("Enbridge", "Crude Oil Commodity Map (effective February 1, "
             "2026), shipper document",
             "https://www.enbridge.com/~/media/Enb/Documents/Shippers/Crude_Oil_Commodity_Map_and_Reference.pdf?la=en"),
        ],
    ),
    dict(
        slug="mine-vs-upgrader-capacity",
        title="Mine capacity vs upgrader capacity",
        deck="Two plants, two numbers. Never blend them.",
        source_line="Heavy Reading research: AER ST39 demonstrated history, verified 2026-09-23",
        body=[
            ("Why there are two numbers", P(
                "An integrated oil sands site is two plants bolted together. "
                "The mine digs up bitumen; the upgrader converts bitumen into "
                "synthetic crude. Each has its own capacity, measured in "
                "different streams: bitumen in, SCO out. Upgrading is not "
                "one-for-one. The observed conversion runs about 0.87 "
                "barrels of SCO per barrel of bitumen feed across the fleet "
                "(0.865 on ST3 data from 2017 to 2026; Horizon 0.888, "
                "Syncrude 0.843, Suncor Base around 0.86 to 0.91). The rest "
                "goes to coke, fuel gas, sulphur, and process losses.")),
            ("Horizon, worked example", P(
                "Horizon carries three stated capacity bases: 264 kb/d of "
                "company operating SCO capacity, 271 kb/d of regulatory SCO "
                "nameplate, and 314 kb/d of mined-bitumen capacity. "
                "Demonstrated history beats all three. The peak monthly SCO "
                "output on record is 309.8 kb/d (November 2025); the peak "
                "mined-bitumen output is 333.3 kb/d (May 2026). For headroom "
                "and utilization math, those demonstrated peaks are the "
                "reference, not the stated figures. (Horizon is 100 percent "
                "CNRL, owned and operated.) Note the peaks are "
                "different months: you cannot divide 309.8 by 333.3 and call "
                "it a yield, because the mine and upgrader do not peak "
                "together.")),
            ("The rule", P(
                "Like for like, always. Compare SCO output to SCO capacity, "
                "and bitumen output to bitumen capacity. A \"capacity\" "
                "number that mixes bitumen-in with SCO-out is meaningless, "
                "and any utilization figure built on it is wrong. Where "
                "stated capacity conflicts with demonstrated output, history "
                "wins, and the page says so explicitly. Non-integrated sites "
                "carry only one of the two numbers: a SAGD project has "
                "bitumen production capacity and no upgrader at all. The "
                "project pages on this site keep the two as separate fields "
                "for exactly this reason, mine capacity in bitumen and "
                "upgrader capacity in SCO, and where a site has only one, "
                "the other field stays empty rather than getting a blended "
                "guess. Horizon's three stated bases (264, 271, and 314) are "
                "kept as separate line items on its page, with the "
                "demonstrated peaks shown alongside them.")),
        ],
        why=("Every utilization and headroom number on this site depends on "
             "this split. Blend the two capacities and you will either "
             "invent spare room that does not exist or hide tightness that "
             "does."),
        sources=[
            ("Heavy Reading research note",
             "Horizon capacity reconciliation: demonstrated ST39 peaks vs "
             "stated bases, verified 2026-09-23 from AER ST39",
             None),
            ("Heavy Reading research note",
             "Upgrader yield study: fleet and plant-level bitumen-to-SCO "
             "yields from AER ST3/ST39, 2017-2026",
             None),
        ],
    ),
    dict(
        slug="sco-grades",
        title="The synthetic grades",
        deck="SYN, Premium Albian, and the other light barrels of the oil sands.",
        source_line="Enbridge shipper documents; crude assay tables",
        body=[
            ("What \"sweet synthetic\" means", P(
                "Synthetic crude is bitumen that has been cracked and "
                "hydrogenated into a refinery-ready light oil. \"Sweet\" "
                "means low sulphur, generally under 0.2 percent. The light "
                "sweet synthetics run 30-plus API with high middle-distillate "
                "yield, which is why refiners pay up for them and why they "
                "trade at a premium to WTI when supply gets tight. In one "
                "August session with upgraders down for maintenance, light "
                "synthetic settled more than $14 a barrel over WTI.")),
            ("The main streams", UL(
                "<b>SYN (Synthetic Sweet Blend)</b>, about 33 API and 0.16 "
                "percent sulphur. The big commingled pool: since May 2014, "
                "Suncor and Syncrude barrels ship as one pool, with SSP "
                "(Syncrude Sweet Premium) as the receipt name.",
                "<b>Premium Albian Synthetic (PAS)</b>, about 35.5 API and "
                "0.04 percent sulphur. The Scotford/AOSP barrel, the sweetest "
                "of the group.",
                "<b>Syncrude Sweet Blend</b>, 30.5 to 33.6 API and 0.07 to "
                "0.13 percent sulphur. The legacy Syncrude grade behind the "
                "SSP receipt name.",
                "<b>CNRL Light Sweet Synthetic Blend (CNS)</b>, 0.15 percent "
                "sulphur. The Horizon barrel.",
                "<b>Albian Heavy Synthetic (AHS)</b>, about 19.6 API and 2.1 "
                "percent sulphur. Not a light synthetic at all: it is a "
                "dilsynbit, a blend of bitumen with synthetic crude, and it "
                "prices with the heavy barrels.")),
            ("Who makes them", P(
                "SYN pools Suncor and Syncrude barrels. Premium Albian comes "
                "from the Scotford upgrader (CNRL 60 percent, Shell 20, "
                "Chevron 20; Shell operates). The CNRL light sweet blend "
                "comes from Horizon, which is 100 percent CNRL.")),
            ("Where they go", P(
                "The light synthetics pool at Edmonton and Hardisty and move "
                "on the big export systems: the Enbridge Mainline to the US "
                "Midwest, Trans Mountain to Burnaby and the West Coast, and "
                "some into local refineries. A large share of the AOSP "
                "barrels never leaves the Edmonton area: it feeds the Shell "
                "Scotford refinery next door to the upgrader.")),
        ],
        why=("SCO is the light barrel in a heavy basin. Unplanned upgrader "
             "outages do two things at once: they remove premium-priced light "
             "supply, and the redirect-and-tilt response adds heavy dilbit "
             "supply. That is the synthetic premium widening while the heavy "
             "differential softens, in one event. Planned turnarounds are "
             "different: the mine plan is set months ahead, so no redirect "
             "is assumed."),
        sources=[
            ("Enbridge", "Crude Oil Commodity Map (effective February 1, "
             "2026), shipper document",
             "https://www.enbridge.com/~/media/Enb/Documents/Shippers/Crude_Oil_Commodity_Map_and_Reference.pdf?la=en"),
            ("Wikipedia", "Western Canadian Select (grade and assay table)",
             "https://en.wikipedia.org/wiki/Western_Canadian_Select"),
            ("BOE Report", "Heavy crude discount deepens, synthetic premium "
             "surges (2022-07-06)",
             "https://boereport.com/2022/07/06/heavy-crude-discount-deepens-synthetic-premium-surges/amp/"),
        ],
    ),
    dict(
        slug="sagd-vs-css-vs-mining",
        title="SAGD vs CSS vs mining",
        deck="The three ways to get bitumen out of the ground.",
        source_line="Heavy Reading research; thermal recovery literature",
        body=[
            ("Mining", P(
                "Truck and shovel. Where the deposit sits close to the "
                "surface, the overburden comes off and the oil sand goes to "
                "a hot-water extraction plant. Only about a fifth of the oil "
                "sands resource is shallow enough to mine; the rest needs "
                "wells. Mined projects: Horizon, Muskeg River, Jackpine, "
                "Kearl, Fort Hills, Suncor Base, and Syncrude's Mildred Lake "
                "and Aurora. Mines are the only source that feeds upgraders "
                "directly, and their output is flat by design until the pit "
                "moves.")),
            ("SAGD", P(
                "Steam-assisted gravity drainage. Two horizontal wells, one "
                "above the other. Steam goes into the top well and forms a "
                "chamber; heated bitumen and condensed water drain down to "
                "the lower well by gravity and get pumped up. It needs a "
                "thick, permeable reservoir and it is the dominant in-situ "
                "method: Foster Creek, Christina Lake (both Cenovus and "
                "MEG), Sunrise, Surmont, Jackfish, Kirby, Leismer, MacKay "
                "River, Firebag, Long Lake, Tucker, Orion, Lindbergh, Great "
                "Divide, BlackGold, Hangingstone, and Blackrod all use it. "
                "The key metric is steam-oil ratio: cubic metres of steam "
                "per cubic metre of bitumen. Canadian SAGD projects run "
                "cumulative ratios of roughly 2.5 to 6, with good operators "
                "around 3. Recovery can exceed half the oil in place, which "
                "is why SAGD won.")),
            ("CSS", P(
                "Cyclic steam stimulation, the original thermal method: huff "
                "and puff. Inject high-pressure steam into a well, shut it "
                "in to soak, then produce from the same well. Repeat. It "
                "works in reservoirs that do not suit SAGD, typically "
                "thinner pay. The trade is efficiency: late in a well's life "
                "the steam-oil ratio runs higher than SAGD. In Alberta it "
                "lives at Imperial's Cold Lake (the largest CSS project in "
                "the oil sands), CNRL's Peace River, and CNRL's Primrose.")),
        ],
        why=("Method sets the decline profile. SAGD pads decline and get "
             "replaced by new pads, so the project is a drilling treadmill. "
             "CSS wells cycle. Mines just run. When you see a project's "
             "forecast shape, you are mostly seeing its extraction method."),
        sources=[
            ("MDPI Energies", "Improving Thermal Efficiency and Reducing "
             "Emissions with CO2 Injection during Late Stage SAGD "
             "Development (SAGD SOR range 2.5-6)",
             "https://www.mdpi.com/2819720"),
            ("ResearchGate", "Cyclic Steam Stimulation (field cases "
             "including Cold Lake)",
             "https://www.researchgate.net/publication/286616425_Cyclic_Steam_Stimulation"),
            ("Digital Refining", "Has the time for partial upgrading of heavy "
             "oil and bitumen arrived? (mineable share of resource)",
             "https://www.digitalrefining.com/article/1000607/has-the-time-for-partial-upgrading-of-heavy-oil-and-bitumen-arrived"),
        ],
    ),
    dict(
        slug="turnarounds",
        title="How turnarounds move barrels",
        deck=("Planned shutdowns, the Horizon September 2026 example, and why "
              "the calendar beats the snapshot."),
        source_line="Heavy Reading research: company budget guidance; AER actuals",
        body=[
            ("What a turnaround is", P(
                "A turnaround is a planned full or partial shutdown for "
                "inspection, maintenance, and equipment replacement. Upgraders "
                "and mines both take them, typically on multi-year cycles, "
                "usually lasting weeks. Unlike an unplanned outage, the "
                "timing and rough size are known in advance: companies put "
                "them in budget guidance and talk about them on earnings "
                "calls. The operator plans and executes the work; at "
                "Horizon that is CNRL.")),
            ("Horizon, September 2026", P(
                "The worked example. CNRL's 2026 budget called a 35-day "
                "Horizon turnaround starting in September, with a 29 kb/d "
                "impact on the annual average: 29 times 365 is 10,585 "
                "thousand barrels of lost production for the year. September "
                "actuals absorbed 6,900 of that (a 230 kb/d bridge for the "
                "month). The remainder, 10,585 minus 6,900, divided by 31 "
                "October days, is 119 kb/d: the October residual in the "
                "model. That is how a single turnaround gets split across "
                "two months without double counting.")),
            ("Why the calendar beats the snapshot", P(
                "Injection-month barrels trade during the prior calendar "
                "month, before nominations. By the time a barrel is being "
                "injected, its trading window is already closed. So the "
                "current outage snapshot is history; what prices the next "
                "tradable barrel is the forward maintenance calendar by "
                "project. That is why this site keeps a forward calendar "
                "and splits it three ways: public-confirmed "
                "(the company stated the number and the timing), "
                "cadence-modeled (an editorially approved estimate from observed "
                "project history, labeled CADENCE-MODELED everywhere, never "
                "as company-confirmed), and guidance-sourced (verified from "
                "guidance or transcripts). Unplanned "
                "outages are a different animal: they hit the current month "
                "with no warning, and the job is to read them in the actuals "
                "and reset the forward calendar. That is why the maintenance "
                "section carries both: the forward calendar for what is "
                "scheduled, and the event log for what actually happened.")),
        ],
        why=("The market does not trade today's outages. It trades the next "
             "year of scheduled downtime, project by project. If your "
             "maintenance view stops at what is offline right now, you are "
             "pricing the wrong month."),
        sources=[
            ("Heavy Reading research note",
             "Horizon September 2026 turnaround bridge: CNRL 2026 budget "
             "guidance vs September actuals, verified 2026-09-23",
             None),
            ("Heavy Reading", "Forward maintenance calendar methodology "
             "(confirmed vs cadence-modeled vs guidance-sourced)",
             None),
        ],
    ),
    dict(
        slug="egress-101",
        title="Egress 101",
        deck=("The pipes out of Alberta, apportionment, and why full pipes "
              "set the price."),
        source_line="Oil Sands Magazine; Canada Energy Regulator",
        body=[
            ("The pipes", P(
                "Five systems carry crude out of landlocked Western Canada. "
                "At year-end 2025 the scoreboard looked like this: Enbridge "
                "Mainline 3,200 kb/d (Edmonton to the US Midwest, with links "
                "to the Gulf Coast, Ontario, and Quebec); Trans Mountain 890 "
                "kb/d (Edmonton to Burnaby and Washington State, after the "
                "590 kb/d TMX expansion started up in May 2024); Keystone "
                "640 kb/d (South Bow, Hardisty to Cushing and the Gulf "
                "Coast); Express 310 kb/d (Hardisty to the Rockies and the "
                "Midwest via Platte); Milk River 98 and Rangeland 20 kb/d "
                "(into Montana). Total nameplate about 5,160 kb/d, or roughly "
                "4,950 of crude once you set aside space for refined "
                "products, NGLs, and US barrels. The Mainline is Enbridge's; "
                "Keystone is operated by South Bow, spun out of TC Energy "
                "in 2024; Trans Mountain is a federal Crown corporation.")),
            ("Apportionment", P(
                "When shippers nominate more barrels than a pipe can take, "
                "the operator prorates everyone. That is apportionment, and "
                "it is the market's way of learning a pipe is full. The "
                "Mainline has been apportioned in most months for years. "
                "Trans Mountain hit apportionment in June 2026, the first "
                "time since the expansion, which tells you the new capacity "
                "got absorbed faster than expected. Full pipes mean barrels "
                "compete for space, and that competition shows up as wider "
                "differentials.")),
            ("Why pipeline fill matters", P(
                "A pipeline is working inventory. The millions of barrels "
                "sitting inside the pipe (line fill) are not in storage and "
                "not available to the market. When a new line starts up, "
                "filling it is a one-time demand event that pulls barrels "
                "out of the tradable pool. After that, line fill just sits "
                "there, quietly holding barrels off the market for as long "
                "as the pipe runs.")),
            ("What is coming", P(
                "No meaningful expansions were planned before 2027. Enbridge "
                "is adding about 150 kb/d of Mainline capacity in late 2026 "
                "to 2027, and Trans Mountain is working on optimization "
                "(drag-reducing agents, new pump stations) aimed at roughly "
                "300 kb/d more by the end of 2028. Alberta has studied a new "
                "million-barrel line to the northwest coast, but no private "
                "company has committed to building it.")),
        ],
        why=("Egress is the hard constraint on the basin. Supply growth "
             "without pipe growth goes straight into the differential. Watch "
             "apportionment: it is the earliest public signal that the "
             "constraint is binding."),
        sources=[
            ("Oil Sands Magazine", "Pipeline Egress Outlook to 2030, 2026 "
             "Edition (2025-12-11)",
             "https://www.oilsandsmagazine.com/market-insights/2025/12/11/pipeline-egress-outlook-to-2030-2026-edition"),
            ("Canada Energy Regulator via Energi Media", "Oil pipeline "
             "Throughputs for 2024, the First Half of 2025",
             "https://energi.media/news/cer-oil-pipeline-throughputs-for-2024-the-first-half-of-2025-remain-high/"),
            ("Reuters via PGJ Online", "Trans Mountain Pipeline Hits Full "
             "Capacity for First Time Since Expansion (June 2026)",
             "https://prodadmin.pgjonline.com/news/2026/june/trans-mountain-pipeline-hits-full-capacity-for-first-time-since-expansion"),
        ],
    ),
    dict(
        slug="z-scores",
        title="Why this site uses z-scores",
        deck=("Raw volume moves mislead. The z-score divides each move by "
              "what is normal for that asset, so the unusual ones stand out."),
        source_line="Heavy Reading methodology",
        body=[
            ("The problem with raw moves", P(
                "A 20 kb/d swing at a 300 kb/d oil sands project is a quiet "
                "month. The same 20 kb/d swing at a 40 kb/d SAGD project is "
                "an emergency. Raw moves in thousand barrels per day (kb/d) "
                "ignore what is normal for the asset, so sorting by raw "
                "change puts the biggest assets at the top every month, "
                "whether anything interesting happened or not. Without a "
                "normalizer, the biggest-movers table would just be a list "
                "of the biggest projects, every single time. Size is not "
                "news.")),
            ("What the score does", P(
                "The z-score divides this month's move by the asset's own "
                "typical monthly swing over the prior year. Every asset gets "
                "judged against itself, on the same scale, from a 300 kb/d "
                "mine to a 30 kb/d thermal project. A score near zero means "
                "business as usual for that asset. A score of 2 or more "
                "means the move was at least twice what that asset normally "
                "does in a month. That is the definition of unusual on this "
                "site: not big in absolute terms, but big relative to the "
                "asset's own history. Standardized moves separate signal "
                "from noise; raw moves cannot.")),
            ("How to read the table", P(
                "The table still sorts by raw change, because size matters "
                "too. The signal flag marks the rows that moved at least "
                "twice their normal monthly range. Read the two together. A "
                "big raw move with a signal flag is the combination that "
                "deserves a trader's attention. A big raw move with no flag "
                "is just a big asset being a big asset. Two caveats. The "
                "score needs history: fewer than six months of month-over-"
                "month changes and the cell reads n/a. And an asset whose "
                "history has zero variance gets no score either, because "
                "you cannot divide by zero. Both render as n/a, never as "
                "zero. The history is the asset's own published actuals "
                "from the Alberta Energy Regulator (AER) monthly statistics, "
                "the same numbers as the Western Canadian Sedimentary Basin "
                "(WCSB) model behind this site. Deterministic, no modeling, "
                "no projections.")),
        ],
        why=("Traders drown in big numbers. The z-score is how you decide "
             "which ones earn your attention: standardize the move against "
             "the asset's own history, and the real surprises stand out "
             "from the routine noise."),
        sources=[
            ("Heavy Reading",
             "Methodology note: z-scores on the biggest-movers table, "
             "verified 2026-09-24",
             None),
        ],
    ),
]


INDEX_INTRO = (
    "The plumbing behind the numbers. Eleven plain-language explainers on how "
    "the oil sands actually works: the plants, the pipes, the ownership, "
    "and the commercial logic. No forecasts, no model output, just the "
    "institutional knowledge that makes the numbers legible. Written for a "
    "new hire on a WCSB desk."
)


def explainer_page(e):
    secs = []
    for h2, html in e["body"]:
        secs.append(f"  <h2>{S.esc(h2)}</h2>\n  {html}")
    secs.append(why(e["why"]))
    secs.append(sources_list(e["sources"]))
    body = "\n".join(secs)
    stamp = (f'  <p class="vintage">Field guide entry &middot; written '
             f'{WRITTEN}.</p>')
    return S.page_shell(
        e["title"], e["title"], e["deck"],
        f'<a href="../index.html">Home</a> / '
        f'<a href="../fieldguide/index.html">Reference</a> / '
        f'<a href="index.html">Field guide</a> / {S.esc(e["title"])}',
        stamp + "\n" + body,
        "fieldguide", 1, WRITTEN, S.esc(e["source_line"]),
        description=e["deck"],
        url_path=f'fieldguide/{e["slug"]}.html')


def index_page():
    items = []
    for i, e in enumerate(EXPLAINERS, 1):
        items.append(
            f'    <li><a href="{e["slug"]}.html"><b>{i}. {S.esc(e["title"])}</b></a>'
            f"<br><span class=\"note\">{S.esc(e['deck'])}</span></li>")
    body = (f'  <p class="sub">{S.esc(INDEX_INTRO)}</p>\n'
            f'  <p class="vintage">Eleven entries &middot; written {WRITTEN}.</p>\n'
            f'  <ol class="ev">\n' + "\n".join(items) + "\n  </ol>")
    return S.page_shell(
        "Field guide", "Field guide", INDEX_INTRO,
        '<a href="../index.html">Home</a> / Reference / Field guide', body,
        "fieldguide", 1, WRITTEN,
        "Company disclosures; AER; CER; Heavy Reading research",
        description="The plumbing behind the numbers: ten plain-language "
                    "explainers on how the oil sands actually works.",
        url_path="fieldguide/index.html")


def build_all():
    FG.mkdir(parents=True, exist_ok=True)
    for e in EXPLAINERS:
        (FG / f"{e['slug']}.html").write_text(explainer_page(e))
        print(f"wrote {FG / e['slug']}.html")
    (FG / "index.html").write_text(index_page())
    print(f"wrote {FG / 'index.html'}")


# ----------------------------------------------------------------------------
# Nav wiring: add "Field guide" to the sitenav block of every existing page.
# The dashboard's nav is hardcoded in its own builder and is left alone.
# ----------------------------------------------------------------------------

def _current_and_depth(path):
    """Derive (nav key, depth) for an existing page from its current nav."""
    text = path.read_text()
    m = re.search(r'<nav class="sitenav" aria-label="Sections">(.*?)</nav>',
                  text, re.S)
    if not m:
        return None
    block = m.group(1)
    tm = re.search(r'<a href="((?:\.\./)*)st3-dashboard\.html"', block)
    depth = tm.group(1).count("../") if tm else 1
    am = re.search(r'<a href="([^"]+)" aria-current="page">', block)
    cur_href = am.group(1) if am else ""
    # At depth > 0 the current nav item links to itself as index.html,
    # so derive the key from the page's directory instead.
    if cur_href == "index.html" and depth > 0:
        d = path.parent.name
        return d, depth
    stripped = re.sub(r"^(\.\./)+", "", cur_href)
    for key, tgt in S._TARGETS.items():
        if stripped == tgt:
            return key, depth
    if path.name == "index.html" and path.parent == SITE:
        return "home", 0
    return None


def wire_nav():
    """Replace the sitenav block on all existing pages (except dashboard)."""
    n = 0
    for path in sorted(SITE.rglob("*.html")):
        if path == SITE / "st3-dashboard.html":
            continue
        if "fieldguide" in path.parts:
            continue
        cd = _current_and_depth(path)
        if not cd:
            continue
        key, depth = cd
        if key not in S.GROUP_OF:
            print(f"  WARN: unknown nav key {key} in {path}, skipped")
            continue
        text = path.read_text()
        new_block = S.nav(key, depth)
        # Replace the WHOLE mobile-nav disclosure (details.mnav wrapper +
        # its summary + sitenav), not just the inner <nav>: S.nav() returns
        # the complete block, so matching only the <nav> nests a second
        # <details class="mnav"> inside the first. The sitenav carries no
        # nested <nav> elements, so the first </nav> after its open tag is
        # its own close; the outer </details> follows.
        new_text, count = re.subn(
            r'<details class="mnav">.*?<nav class="sitenav" '
            r'aria-label="Sections">.*?</nav>\s*</details>',
            lambda m: new_block, text, count=1, flags=re.S)
        if count:
            path.write_text(new_text)
            n += 1
    print(f"rewired nav on {n} pages")


def check_copy():
    """No em dashes, no 'it's not X, it's Y' in the new section."""
    bad = []
    for e in EXPLAINERS:
        blob = " ".join([e["title"], e["deck"]] +
                        [h for _, h in e["body"]] +
                        [b for _, b in e["body"]] + [e["why"]])
        if "\u2014" in blob or "--" in re.sub(r"<[^>]+>", "", blob):
            bad.append((e["slug"], "em dash"))
        low = re.sub(r"<[^>]+>", "", blob).lower()
        if re.search(r"it'?s not .{1,40}?,? it'?s ", low):
            bad.append((e["slug"], "it's-not-it's"))
    # word counts
    for e in EXPLAINERS:
        words = len(re.sub(r"<[^>]+>", " ",
                           " ".join(b for _, b in e["body"]) + e["why"]).split())
        print(f"  {e['slug']}: {words} words")
        if not 300 <= words <= 600:
            bad.append((e["slug"], f"word count {words}"))
    if bad:
        print("COPY CHECK FAILURES:", bad)
        raise SystemExit(1)
    print("copy checks passed")


def main():
    check_copy()
    build_all()
    wire_nav()
    print("field guide built")


if __name__ == "__main__":
    main()
