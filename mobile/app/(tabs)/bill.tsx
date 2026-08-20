import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import {
  assertHeliosConfigured,
  HELIOS_API_BASE,
  HELIOS_API_HEADERS,
} from '@/constants/helios';
import {
  estimateMeralcoBill,
  MERALCO_METER_REFERENCE,
  MERALCO_MODEL,
  MERALCO_REFERENCE_BILLS,
} from '@/constants/meralco';

type BillingProfile = {
  billing_period: string;
  period_end: string;
  consumption_kwh: number;
  energy_amount_php: number;
  other_charges_php: number;
  total_amount_php: number;
  previous_meter_reading: number;
  current_meter_reading: number;
  import_rate_php_per_kwh: number;
  export_rate_php_per_kwh: number | null;
  confirmed_meter_reading?: number | null;
  carried_credit_php: number | null;
};

const peso = new Intl.NumberFormat('en-PH', {
  style: 'currency',
  currency: 'PHP',
  maximumFractionDigits: 0,
});

export default function BillScreen() {
  const [gridImport, setGridImport] = useState(
    String(
      MERALCO_METER_REFERENCE.currentReadingKwh -
        MERALCO_METER_REFERENCE.previousReadingKwh,
    ),
  );
  const [gridExport, setGridExport] = useState('0');
  const [exportRate, setExportRate] = useState(
    '0',
  );
  const [appliedCredits, setAppliedCredits] = useState('0');
  const [elapsedDays, setElapsedDays] = useState(
    String(MERALCO_METER_REFERENCE.elapsedDays),
  );
  const [cycleDays, setCycleDays] = useState(
    String(MERALCO_METER_REFERENCE.cycleDays),
  );
  const [billingProfile, setBillingProfile] = useState<BillingProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadGridImport = useCallback(async () => {
    try {
      setError(null);
      assertHeliosConfigured();
      const response = await fetch(
        `${HELIOS_API_BASE.replace('/energy', '')}/billing/current-cycle`,
        { headers: HELIOS_API_HEADERS },
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail ?? `Billing API returned ${response.status}`);
      }
      setGridImport(data.grid_import_kwh.toFixed(1));
      setGridExport(data.grid_export_kwh.toFixed(1));
      setElapsedDays(String(data.elapsed_days));
      setCycleDays(String(data.cycle_days));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Unable to load grid import',
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadGridImport();
    const interval = setInterval(
      () => loadGridImport(),
      15 * 60 * 1000,
    );
    return () => clearInterval(interval);
  }, [loadGridImport]);

  useEffect(() => {
    const loadBillingProfile = async () => {
      try {
        const response = await fetch(
          `${HELIOS_API_BASE.replace('/energy', '')}/billing/profile`,
          { headers: HELIOS_API_HEADERS },
        );
        if (response.ok) {
          const profile: BillingProfile = await response.json();
          setBillingProfile(profile);
          setAppliedCredits(Number(profile.carried_credit_php ?? 0).toFixed(2));
          if (profile.export_rate_php_per_kwh !== null) {
            setExportRate(profile.export_rate_php_per_kwh.toFixed(4));
          } else {
            setExportRate('0');
          }
        }
      } catch {
        // The estimator can still use its calibrated local fallback.
      }
    };
    loadBillingProfile();
  }, []);

  const estimate = useMemo(
    () => estimateMeralcoBill({
      gridImportKwh: Number(gridImport) || 0,
      gridExportKwh: Number(gridExport) || 0,
      exportRatePhpPerKwh: Number(exportRate) || 0,
      appliedCreditsPhp: Number(appliedCredits) || 0,
      importRatePhpPerKwh:
        billingProfile?.import_rate_php_per_kwh ??
        MERALCO_MODEL.weightedEnergyRatePhpPerKwh,
      otherChargesPhp:
        billingProfile?.other_charges_php ??
        MERALCO_MODEL.recurringOtherChargesPhp,
      elapsedDays: Number(elapsedDays) || 1,
      cycleDays: Number(cycleDays) || MERALCO_MODEL.defaultCycleDays,
      includeOtherCharges: true,
    }),
    [
      appliedCredits,
      cycleDays,
      elapsedDays,
      exportRate,
      gridExport,
      gridImport,
      billingProfile,
    ],
  );

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#FDB813" />
        <Text style={styles.muted}>Loading Meralco estimate...</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}>
      <Text style={styles.title}>Meralco estimate</Text>
      <Text style={styles.subtitle}>
        Projection calibrated from your last two bills
      </Text>

      {error && <Text style={styles.error}>{error}</Text>}

      {billingProfile && (
        <Text style={styles.profileNotice}>
          Last verified Meralco basis: {billingProfile.billing_period} · {billingProfile.consumption_kwh.toFixed(0)} kWh · ₱{billingProfile.import_rate_php_per_kwh.toFixed(2)}/kWh
        </Text>
      )}

      <View style={styles.heroCard}>
        <Text style={styles.eyebrow}>PROJECTED BILL</Text>
        <Text style={styles.heroValue}>{peso.format(estimate.projectedPhp)}</Text>
        <Text style={styles.heroCaption}>
          {billingProfile
            ? 'Using the last verified Meralco rates and automatic Solis readings'
            : `Expected range ${peso.format(estimate.lowPhp)} - ${peso.format(estimate.highPhp)}`}
        </Text>
        <View style={styles.divider} />
        <View style={styles.row}>
          <Metric label="Month to date" value={peso.format(estimate.monthToDatePhp)} />
          <Metric label="Projected import" value={`${estimate.projectedKwh.toFixed(0)} kWh`} />
        </View>
        <View style={styles.zeroTarget}>
          <Text style={styles.zeroTargetLabel}>ZERO-BILL TARGET</Text>
          <Text style={styles.zeroTargetValue}>
            {estimate.additionalExportForZeroKwh === null
              ? 'Waiting for official export rate'
              : estimate.additionalExportForZeroKwh > 0
                ? `${estimate.additionalExportForZeroKwh.toFixed(0)} kWh more export`
                : estimate.projectedAvailableCreditPhp >= estimate.projectedGrossPhp
                  ? 'On track for ₱0'
                  : 'Not enough data yet'}
          </Text>
          {estimate.additionalExportForZeroKwh === null && (
            <Text style={styles.hint}>
              No export credit is assumed until your own net-metering bill provides the rate.
            </Text>
          )}
        </View>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Export credit balance</Text>
        {Number(exportRate) > 0 ? (
          <>
            <View style={styles.row}>
              <Metric
                label="Projected export credit"
                value={peso.format(estimate.projectedExportCreditPhp)}
              />
              <Metric
                label="Credit applied"
                value={peso.format(estimate.projectedCreditAppliedPhp)}
              />
            </View>
            <View style={styles.creditBalance}>
              <Text style={styles.creditBalanceLabel}>ESTIMATED REMAINING CREDIT</Text>
              <Text style={styles.creditBalanceValue}>
                {peso.format(estimate.projectedRemainingCreditPhp)}
              </Text>
            </View>
            <Text style={styles.disclaimer}>
              Meralco remains the authority for the official carried balance. Helios updates energy automatically from Solis.
            </Text>
          </>
        ) : (
          <Text style={styles.disclaimer}>
            Waiting for your own net-metering bill to provide the official export-credit rate. No sample rate is being assumed.
          </Text>
        )}
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Model basis</Text>
        <Text style={styles.body}>
          Import energy rate: ₱{(billingProfile?.import_rate_php_per_kwh ?? MERALCO_MODEL.weightedEnergyRatePhpPerKwh).toFixed(2)}/kWh
        </Text>
        <Text style={styles.body}>
          Export credit: {estimate.projectedExportKwh.toFixed(0)} kWh × ₱{(Number(exportRate) || 0).toFixed(2)} = {peso.format(estimate.projectedExportCreditPhp)}
        </Text>
        {MERALCO_REFERENCE_BILLS.map(bill => (
          <View key={bill.period} style={styles.referenceRow}>
            <Text style={styles.referencePeriod}>{bill.period}</Text>
            <Text style={styles.referenceValue}>
              {bill.consumptionKwh} kWh · {peso.format(bill.totalPhp)}
            </Text>
          </View>
        ))}
        <Text style={styles.disclaimer}>
          Estimate only. Meralco email summaries do not include detailed meter readings, import rates, export rates, or net-metering credits, so Helios retains the last verified billing values and adds automatic Solis import/export measurements. Meralco remains the official source.
        </Text>
      </View>
    </ScrollView>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#071117' },
  content: { padding: 20, paddingTop: 64, paddingBottom: 40, gap: 16 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, backgroundColor: '#071117' },
  title: { color: '#F5F7F8', fontSize: 32, fontWeight: '800' },
  subtitle: { color: '#8FA1AC', fontSize: 15, marginTop: -10 },
  muted: { color: '#8FA1AC' },
  error: { color: '#FF8D8D', backgroundColor: '#32191C', padding: 12, borderRadius: 12 },
  profileNotice: { color: '#8FDDBA', backgroundColor: '#10251D', padding: 12, borderRadius: 12, fontSize: 12 },
  heroCard: { backgroundColor: '#0D1820', borderRadius: 22, padding: 22, borderWidth: 1, borderColor: '#20303A' },
  eyebrow: { color: '#FDB813', fontSize: 12, fontWeight: '800', letterSpacing: 1.2 },
  heroValue: { color: '#F5F7F8', fontSize: 42, fontWeight: '800', marginTop: 8 },
  heroCaption: { color: '#9AAAB3', marginTop: 4 },
  divider: { height: 1, backgroundColor: '#20303A', marginVertical: 18 },
  row: { flexDirection: 'row', gap: 12 },
  metric: { flex: 1 },
  metricLabel: { color: '#778A95', fontSize: 12 },
  metricValue: { color: '#F5F7F8', fontSize: 17, fontWeight: '700', marginTop: 4 },
  zeroTarget: { marginTop: 18, paddingTop: 16, borderTopWidth: 1, borderTopColor: '#20303A' },
  zeroTargetLabel: { color: '#52D39A', fontSize: 11, fontWeight: '800', letterSpacing: 1.1 },
  zeroTargetValue: { color: '#F5F7F8', fontSize: 20, fontWeight: '700', marginTop: 5 },
  card: { backgroundColor: '#0D1820', borderRadius: 18, padding: 18, borderWidth: 1, borderColor: '#172832', gap: 14 },
  cardTitle: { color: '#F5F7F8', fontSize: 19, fontWeight: '700' },
  creditBalance: { backgroundColor: '#10251D', borderRadius: 13, padding: 14 },
  creditBalanceLabel: { color: '#72CFA4', fontSize: 11, fontWeight: '800', letterSpacing: 1 },
  creditBalanceValue: { color: '#F5F7F8', fontSize: 28, fontWeight: '800', marginTop: 5 },
  hint: { color: '#71838E', fontSize: 12 },
  body: { color: '#CCD4D8', lineHeight: 20 },
  referenceRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 10 },
  referencePeriod: { color: '#8597A1', flex: 1, fontSize: 12 },
  referenceValue: { color: '#DDE3E6', fontSize: 12, fontWeight: '600' },
  disclaimer: { color: '#71838E', fontSize: 12, lineHeight: 17, marginTop: 2 },
});
