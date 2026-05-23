// Mock data for the dashboard.

const SEED_RUNS = [
  {
    id: 'run_2026-05-23T15-04', lbId: 'LB-0038', taskName: 'epistasis_ternary',
    status: 'complete', model: 'longevity-llm', n: 200, completed: 200, errors: 0,
    f1: 0.62, ci: [0.58, 0.66], bal_acc: 0.59, mae: null, faithfulness: 0.81,
    started: '2026-05-23T15:04Z', durationS: 612, think: true,
    spark: [0.42, 0.48, 0.51, 0.55, 0.58, 0.60, 0.61, 0.62],
  },
  {
    id: 'run_2026-05-23T13-22', lbId: 'LB-0042', taskName: 'lifespan_mae',
    status: 'complete', model: 'longevity-llm', n: 150, completed: 150, errors: 1,
    f1: null, ci: null, bal_acc: null, mae: 11.4, faithfulness: 0.76,
    started: '2026-05-23T13:22Z', durationS: 482, think: false,
    spark: [0.30, 0.40, 0.45, 0.52, 0.54, 0.55, 0.56, 0.58],
  },
  {
    id: 'run_2026-05-23T11-08', lbId: 'LB-0038', taskName: 'epistasis_ternary',
    status: 'running', model: 'gpt-4o', n: 200, completed: 84, errors: 0,
    f1: 0.58, ci: null, bal_acc: 0.55, mae: null, faithfulness: null,
    started: '2026-05-23T11:08Z', durationS: 312, think: false,
    spark: [0.38, 0.42, 0.48, 0.52, 0.55, 0.56, 0.57, 0.58],
  },
  {
    id: 'run_2026-05-23T10-44', lbId: 'LB-0051', taskName: 'gene_pathway_mcq',
    status: 'failed', model: 'longevity-llm', n: 50, completed: 12, errors: 38,
    f1: null, ci: null, bal_acc: null, mae: null, faithfulness: null,
    started: '2026-05-23T10:44Z', durationS: 81, think: true,
    spark: [0.5, 0.4, 0.3, 0.2, 0.1, 0.05, 0.05, 0.05],
  },
  {
    id: 'run_2026-05-23T09-12', lbId: 'LB-0067', taskName: 'organism_pairwise',
    status: 'complete', model: 'longevity-llm', n: 100, completed: 100, errors: 0,
    f1: 0.71, ci: [0.66, 0.76], bal_acc: 0.68, mae: null, faithfulness: 0.84,
    started: '2026-05-23T09:12Z', durationS: 421, think: true,
    spark: [0.55, 0.60, 0.63, 0.66, 0.68, 0.70, 0.70, 0.71],
  },
  {
    id: 'run_2026-05-22T20-31', lbId: 'LB-0038', taskName: 'epistasis_ternary',
    status: 'complete', model: 'majority-baseline', n: 200, completed: 200, errors: 0,
    f1: 0.42, ci: [0.38, 0.46], bal_acc: 0.33, mae: null, faithfulness: null,
    started: '2026-05-22T20:31Z', durationS: 3, think: false,
    spark: [0.42, 0.42, 0.42, 0.42, 0.42, 0.42, 0.42, 0.42],
  },
];

const SEED_RECORDS = [
  {
    row: 3, lbId: 'LB-0038', format: 'ternary_classification', metric: 'macro_f1',
    organism: 'C. elegans', gene1: 'daf-2', gene2: 'age-1',
    gold: 'synergistic', pred: 'synergistic', match: true,
    latencyS: 4.21, tokens: 384, consistent: true, faithfulness: 0.91,
    sourceDb: 'SynergyAge', sourceId: 'SYN-0042',
    userMsg: 'In C. elegans, daf-2 single loss-of-function extends lifespan by ~100% and age-1 single loss-of-function extends lifespan by ~100%. The double mutant daf-2; age-1 also extends lifespan by ~100% relative to wild-type, not 200%. Classify this epistasis: synergistic, antagonistic, or additive.',
    trace: 'The interaction between [GENE]daf-2[/GENE] (insulin receptor) and [GENE]age-1[/GENE] (PI3K) in C. elegans is well-characterized. Both function in the IIS pathway upstream of [GENE]daf-16[/GENE]. Single-gene loss-of-function each [V]extends lifespan[/V] by ~100%. The double mutant shows the same magnitude — daf-2 and age-1 are in the same linear pathway, so the second mutation adds no further benefit. This is the textbook definition of an [V]epistatic / non-additive relationship[/V] where one gene masks the other.',
  },
  {
    row: 4, lbId: 'LB-0038', format: 'ternary_classification', metric: 'macro_f1',
    organism: 'C. elegans', gene1: 'clk-1', gene2: 'isp-1',
    gold: 'additive', pred: 'synergistic', match: false,
    latencyS: 6.04, tokens: 512, consistent: true, faithfulness: 0.78,
    sourceDb: 'SynergyAge', sourceId: 'SYN-0091',
    userMsg: 'Partial loss-of-function of clk-1 (Q-cycle, mitochondrial) extends lifespan by 35%. isp-1 partial loss extends by 65%. The double mutant extends by ~98%. Classify.',
    trace: 'Both [GENE]clk-1[/GENE] and [GENE]isp-1[/GENE] are mitochondrial. Single mutants [V]extend lifespan[/V]. Sum of single effects is 35 + 65 = 100%. Double = 98%, very close to sum. This is [V]additive[/V]... actually 98 is slightly less than sum, but within noise. I will say [F]synergistic[/F] because both target ETC.',
  },
  {
    row: 5, lbId: 'LB-0038', format: 'regression', metric: 'mae',
    organism: 'D. melanogaster', gene1: 'FOXO', gene2: 'TOR',
    gold: '−23.5', pred: '−11.2', match: false,
    latencyS: 7.88, tokens: 612, consistent: false, faithfulness: 0.41,
    sourceDb: 'SynergyAge', sourceId: 'SYN-0203',
    userMsg: 'Predict the combined lifespan percent change for FOXO overexpression + TOR knockdown in D. melanogaster.',
    trace: 'Hmm. [GENE]FOXO[/GENE] overexpression in fly extends lifespan. [GENE]TOR[/GENE] knockdown also extends. Combined should be more [V]extending[/V]... but the question says percent change, and the sign convention here is increase = positive. I will [F]predict shortening[/F] because TOR is essential.',
  },
  {
    row: 6, lbId: 'LB-0042', format: 'binary_classification', metric: 'macro_f1',
    organism: 'Mus musculus', gene1: 'Trp53', gene2: 'Igf1r',
    gold: 'decreased', pred: 'decreased', match: true,
    latencyS: 5.12, tokens: 298, consistent: true, faithfulness: 0.88,
    sourceDb: 'MGI', sourceId: 'MGI:97049',
    userMsg: 'A C57BL/6J mouse has a targeted Trp53 gain-of-function allele combined with Igf1r heterozygous knockout. Does the median lifespan increase, decrease, or stay roughly constant compared to wild-type?',
    trace: '[GENE]Trp53[/GENE] gain-of-function in mouse [V]decreases lifespan[/V] (premature aging via excess apoptosis). [GENE]Igf1r[/GENE] heterozygous typically [V]extends lifespan[/V] modestly. Combined: the p53 effect dominates. Answer: decreased.',
  },
  {
    row: 7, lbId: 'LB-0042', format: 'ternary_classification', metric: 'macro_f1',
    organism: 'Mus musculus', gene1: 'Sirt1', gene2: 'Atg7',
    gold: 'no_change', pred: 'no_change', match: true,
    latencyS: 5.92, tokens: 410, consistent: true, faithfulness: 0.82,
    sourceDb: 'MGI', sourceId: 'MGI:00231',
    userMsg: 'Sirt1 overexpression + Atg7 conditional knockout in liver. Lifespan phenotype?',
    trace: '[GENE]Sirt1[/GENE] OE alone is neutral-to-slightly-positive. [GENE]Atg7[/GENE] cKO in liver impairs autophagy, but tissue-specific so mild. Net: [V]no significant lifespan change[/V].',
  },
  {
    row: 8, lbId: 'LB-0038', format: 'mcq', metric: 'accuracy',
    organism: 'C. elegans', gene1: 'eat-2', gene2: 'rsks-1',
    gold: 'B', pred: 'B', match: true,
    latencyS: 3.84, tokens: 224, consistent: true, faithfulness: 0.94,
    sourceDb: 'SynergyAge', sourceId: 'SYN-0118',
    userMsg: 'Which combination is most likely epistatic (single masks second)?  A: daf-2; daf-16  B: eat-2; rsks-1  C: hsf-1; sod-3  D: glp-1; daf-12',
    trace: 'Eat-2 acts via dietary restriction. Rsks-1 (S6K) is downstream in TOR. DR → TOR → S6K. So eat-2 and rsks-1 are in the same linear pathway → epistatic. B.',
  },
];

const ENTITY_HIGHLIGHTS = (text) =>
  text
    .replace(/\[GENE\](.+?)\[\/GENE\]/g, '<span class="gene">$1</span>')
    .replace(/\[V\](.+?)\[\/V\]/g, '<span class="verify">$1</span>')
    .replace(/\[F\](.+?)\[\/F\]/g, '<span class="fail">$1</span>');

Object.assign(window, { SEED_RUNS, SEED_RECORDS, ENTITY_HIGHLIGHTS });
