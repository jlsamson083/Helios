export const MERALCO_REFERENCE_BILLS = [
  {
    period: '29 May - 28 Jun 2026',
    consumptionKwh: 922,
    energyAmountPhp: 14422.03,
    otherChargesPhp: 186.19,
    totalPhp: 14608.22,
  },
  {
    period: '29 Jun - 28 Jul 2026',
    consumptionKwh: 878,
    energyAmountPhp: 14036.01,
    otherChargesPhp: 186.19,
    totalPhp: 14222.20,
  },
] as const;

const totalReferenceEnergy = MERALCO_REFERENCE_BILLS.reduce(
  (sum, bill) => sum + bill.energyAmountPhp,
  0,
);

const totalReferenceKwh = MERALCO_REFERENCE_BILLS.reduce(
  (sum, bill) => sum + bill.consumptionKwh,
  0,
);

export const MERALCO_MODEL = {
  weightedEnergyRatePhpPerKwh:
    totalReferenceEnergy / totalReferenceKwh,
  lowEnergyRatePhpPerKwh: Math.min(
    ...MERALCO_REFERENCE_BILLS.map(
      bill => bill.energyAmountPhp / bill.consumptionKwh,
    ),
  ),
  highEnergyRatePhpPerKwh: Math.max(
    ...MERALCO_REFERENCE_BILLS.map(
      bill => bill.energyAmountPhp / bill.consumptionKwh,
    ),
  ),
  recurringOtherChargesPhp: 186.19,
  sampleNetMeteringExportRatePhpPerKwh: 9.27,
  defaultCycleDays: 30,
} as const;

export const MERALCO_METER_REFERENCE = {
  previousReadingKwh: 8252,
  currentReadingKwh: 8350,
  readingDate: '14 Aug 2026, about 6:00 PM',
  cycleStart: '29 Jul 2026',
  cycleEnd: '28 Aug 2026',
  elapsedDays: 17,
  cycleDays: 31,
} as const;

export function estimateMeralcoBill({
  gridImportKwh,
  gridExportKwh = 0,
  exportRatePhpPerKwh = MERALCO_MODEL.sampleNetMeteringExportRatePhpPerKwh,
  appliedCreditsPhp = 0,
  importRatePhpPerKwh = MERALCO_MODEL.weightedEnergyRatePhpPerKwh,
  otherChargesPhp = MERALCO_MODEL.recurringOtherChargesPhp,
  elapsedDays,
  cycleDays,
  includeOtherCharges = true,
}: {
  gridImportKwh: number;
  gridExportKwh?: number;
  exportRatePhpPerKwh?: number;
  appliedCreditsPhp?: number;
  importRatePhpPerKwh?: number;
  otherChargesPhp?: number;
  elapsedDays: number;
  cycleDays: number;
  includeOtherCharges?: boolean;
}) {
  const safeImport = Math.max(gridImportKwh, 0);
  const safeExport = Math.max(gridExportKwh, 0);
  const safeExportRate = Math.max(exportRatePhpPerKwh, 0);
  const safeAppliedCredits = Math.max(appliedCreditsPhp, 0);
  const safeImportRate = Math.max(importRatePhpPerKwh, 0);
  const safeElapsed = Math.max(elapsedDays, 1);
  const safeCycle = Math.max(cycleDays, safeElapsed);
  const projectedKwh = safeImport * (safeCycle / safeElapsed);
  const projectedExportKwh = safeExport * (safeCycle / safeElapsed);
  const otherCharges = includeOtherCharges
    ? Math.max(otherChargesPhp, 0)
    : 0;

  const monthToDateGrossPhp =
      safeImport * safeImportRate +
      otherCharges;
  const projectedGrossPhp =
      projectedKwh * safeImportRate +
      otherCharges;
  const monthToDateExportCreditPhp = safeExport * safeExportRate;
  const projectedExportCreditPhp = projectedExportKwh * safeExportRate;
  const projectedAvailableCreditPhp =
    projectedExportCreditPhp + safeAppliedCredits;

  return {
    monthToDatePhp: Math.max(
      monthToDateGrossPhp - monthToDateExportCreditPhp - safeAppliedCredits,
      0,
    ),
    projectedKwh,
    projectedExportKwh,
    projectedExportCreditPhp,
    projectedGrossPhp,
    projectedAvailableCreditPhp,
    projectedCreditAppliedPhp: Math.min(
      projectedGrossPhp,
      projectedAvailableCreditPhp,
    ),
    projectedRemainingCreditPhp: Math.max(
      projectedAvailableCreditPhp - projectedGrossPhp,
      0,
    ),
    projectedPhp: Math.max(
      projectedGrossPhp - projectedExportCreditPhp - safeAppliedCredits,
      0,
    ),
    lowPhp: Math.max(
      projectedKwh * safeImportRate +
      otherCharges - projectedExportCreditPhp - safeAppliedCredits,
      0,
    ),
    highPhp: Math.max(
      projectedKwh * safeImportRate +
      otherCharges - projectedExportCreditPhp - safeAppliedCredits,
      0,
    ),
    additionalExportForZeroKwh:
      safeExportRate > 0
        ? Math.max(
          (projectedGrossPhp - safeAppliedCredits) / safeExportRate -
            projectedExportKwh,
          0,
        )
        : null,
  };
}
