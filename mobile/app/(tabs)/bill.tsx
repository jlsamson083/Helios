import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import * as DocumentPicker from 'expo-document-picker';

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

type HistoryResponse = {
  month: {
    grid_import_kwh: number;
    grid_export_kwh: number;
  };
};

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

type DataQuality = {
  freshness: 'fresh' | 'delayed' | 'stale' | 'unavailable';
  confidence: 'high' | 'medium' | 'low';
  latestSolisAt: string | null;
  ageMinutes: number | null;
  sampleDays: number;
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
  const [importSource, setImportSource] = useState<'meter' | 'solis'>('meter');
  const [billingProfile, setBillingProfile] = useState<BillingProfile | null>(null);
  const [uploading, setUploading] = useState(false);
  const [currentMeterReading, setCurrentMeterReading] = useState('8350');
  const [confirmingMeter, setConfirmingMeter] = useState(false);
  const [confirmedImport, setConfirmedImport] = useState(98);
  const [estimatedImport, setEstimatedImport] = useState(0);
  const [includeOtherCharges, setIncludeOtherCharges] = useState(true);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dataQuality, setDataQuality] = useState<DataQuality | null>(null);

  const loadGridImport = useCallback(async (useSolisImport = true) => {
    try {
      setError(null);
      assertHeliosConfigured();
      if (useSolisImport) {
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
        setConfirmedImport(data.confirmed_grid_import_kwh);
        setEstimatedImport(data.estimated_grid_import_kwh);
        setDataQuality({
          freshness: data.data_freshness,
          confidence: data.data_confidence,
          latestSolisAt: data.latest_solis_at,
          ageMinutes: data.solis_age_minutes,
          sampleDays: data.sample_days,
        });
        setImportSource('solis');
        return;
      }
      const response = await fetch(
        `${HELIOS_API_BASE}/history/summary`,
        { headers: HELIOS_API_HEADERS },
      );
      if (!response.ok) {
        throw new Error(`History API returned ${response.status}`);
      }
      const data: HistoryResponse = await response.json();
      setGridExport(data.month.grid_export_kwh.toFixed(1));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Unable to load grid import',
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadGridImport(true);
    const interval = setInterval(
      () => loadGridImport(true),
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
          setCurrentMeterReading(
            String(profile.confirmed_meter_reading ?? profile.current_meter_reading),
          );
          if (profile.export_rate_php_per_kwh !== null) {
            setExportRate(profile.export_rate_php_per_kwh.toFixed(4));
          } else {
            setExportRate('0');
          }
        }
      } catch {
        // The estimator can still use its local fallback until a bill is uploaded.
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
      includeOtherCharges,
    }),
    [
      appliedCredits,
      cycleDays,
      elapsedDays,
      exportRate,
      gridExport,
      gridImport,
      includeOtherCharges,
      billingProfile,
    ],
  );

  const uploadLatestBill = async () => {
    try {
      setUploading(true);
      setError(null);
      const result = await DocumentPicker.getDocumentAsync({
        type: 'application/pdf',
        copyToCacheDirectory: true,
      });
      if (result.canceled) return;

      const fileResponse = await fetch(result.assets[0].uri);
      const pdf = await fileResponse.blob();
      const response = await fetch(
        `${HELIOS_API_BASE.replace('/energy', '')}/billing/upload`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/pdf',
            ...HELIOS_API_HEADERS,
          },
          body: pdf,
        },
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail ?? `Upload returned ${response.status}`);
      }

      const profile = data as BillingProfile;
      setBillingProfile(profile);
      setAppliedCredits(Number(profile.carried_credit_php ?? 0).toFixed(2));
      setGridImport('0');
      setGridExport('0');
      setImportSource('meter');
      setElapsedDays('1');
      setCycleDays('30');
      setCurrentMeterReading(String(profile.current_meter_reading));
      setConfirmedImport(0);
      setEstimatedImport(0);
      if (profile.export_rate_php_per_kwh !== null) {
        setExportRate(profile.export_rate_php_per_kwh.toFixed(4));
      } else {
        setExportRate('0');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to upload bill');
    } finally {
      setUploading(false);
    }
  };

  const confirmMeterReading = async () => {
    try {
      setConfirmingMeter(true);
      setError(null);
      const response = await fetch(
        `${HELIOS_API_BASE.replace('/energy', '')}/billing/meter-reconciliation`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            ...HELIOS_API_HEADERS,
          },
          body: JSON.stringify({
            current_meter_reading: Number(currentMeterReading),
          }),
        },
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail ?? `Meter update returned ${response.status}`);
      }
      setConfirmedImport(data.confirmed_grid_import_kwh);
      setEstimatedImport(0);
      setGridImport(data.confirmed_grid_import_kwh.toFixed(1));
      await loadGridImport(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to confirm meter reading');
    } finally {
      setConfirmingMeter(false);
    }
  };

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
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => {
            setRefreshing(true);
            loadGridImport(true);
          }}
          tintColor="#FDB813"
        />
      }>
      <Text style={styles.title}>Meralco estimate</Text>
      <Text style={styles.subtitle}>
        Projection calibrated from your last two bills
      </Text>

      {error && <Text style={styles.error}>{error}</Text>}

      <Pressable
        style={styles.uploadButton}
        onPress={uploadLatestBill}
        disabled={uploading}>
        <Text style={styles.uploadTitle}>
          {uploading ? 'Reading bill…' : 'Upload latest Meralco PDF'}
        </Text>
        <Text style={styles.uploadHint}>
          Extracts rates and readings, then discards the document
        </Text>
      </Pressable>

      {billingProfile && (
        <Text style={styles.profileNotice}>
          Using {billingProfile.billing_period} · {billingProfile.consumption_kwh.toFixed(0)} kWh · ₱{billingProfile.import_rate_php_per_kwh.toFixed(2)}/kWh
        </Text>
      )}

      {billingProfile && dataQuality && (
        <View style={styles.qualityCard}>
          <View style={styles.qualityHeader}>
            <Text style={styles.qualityTitle}>Projection data quality</Text>
            <Text style={[
              styles.qualityBadge,
              dataQuality.freshness === 'fresh'
                ? styles.qualityFresh
                : dataQuality.freshness === 'delayed'
                  ? styles.qualityDelayed
                  : styles.qualityStale,
            ]}>
              {dataQuality.freshness.toUpperCase()}
            </Text>
          </View>
          <Text style={styles.body}>
            {dataQuality.confidence.toUpperCase()} confidence · {dataQuality.sampleDays} measured day{dataQuality.sampleDays === 1 ? '' : 's'}
          </Text>
          <Text style={styles.hint}>
            {dataQuality.ageMinutes === null
              ? 'No Solis measurement has been recorded since the uploaded bill baseline.'
              : `Latest Solis measurement was ${dataQuality.ageMinutes} minute${dataQuality.ageMinutes === 1 ? '' : 's'} ago.`}
          </Text>
          <Text style={styles.hint}>
            Basis: your latest uploaded bill plus measured Solis import and export only.
          </Text>
        </View>
      )}

      <View style={styles.heroCard}>
        <Text style={styles.eyebrow}>PROJECTED BILL</Text>
        <Text style={styles.heroValue}>{peso.format(estimate.projectedPhp)}</Text>
        <Text style={styles.heroCaption}>
          {billingProfile
            ? 'Using the rates extracted from your latest uploaded bill'
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
        <Text style={styles.cardTitle}>Billing inputs</Text>
        <View style={styles.sourceBadge}>
          <Text style={styles.sourceBadgeText}>
            {billingProfile
              ? `UPLOADED BILL · CLOSED AT ${billingProfile.current_meter_reading.toFixed(0)} kWh`
              : importSource === 'meter'
              ? `METER PHOTO · 8,350 − 8,252 = 98 kWh · ${MERALCO_METER_REFERENCE.readingDate}`
              : 'SOLIS IMPORT/EXPORT SINCE LAST BILL UPLOAD'}
          </Text>
        </View>
        <View style={styles.readOnlyEnergy}>
          <View style={styles.readOnlyCopy}>
            <Text style={styles.fieldLabel}>Grid import used for estimate</Text>
            <Text style={styles.hint}>
              Confirmed meter usage plus subsequent Solis import
            </Text>
          </View>
          <Text style={styles.readOnlyValue}>{Number(gridImport).toFixed(1)} kWh</Text>
        </View>
        {billingProfile && (
          <View style={styles.meterBox}>
            <Text style={styles.fieldLabel}>
              Current Meralco meter reading
            </Text>
            <Field
              label={`Uploaded bill closed at ${billingProfile.current_meter_reading.toFixed(0)} kWh`}
              value={currentMeterReading}
              onChange={setCurrentMeterReading}
              suffix="kWh"
            />
            <Pressable
              style={styles.confirmButton}
              onPress={confirmMeterReading}
              disabled={confirmingMeter}>
              <Text style={styles.confirmButtonText}>
                {confirmingMeter ? 'Confirming…' : 'Confirm meter reading'}
              </Text>
            </Pressable>
            <Text style={styles.hint}>
              Meter-confirmed: {confirmedImport.toFixed(1)} kWh · Solis-estimated afterward: {estimatedImport.toFixed(1)} kWh
            </Text>
          </View>
        )}
        <View style={styles.readOnlyEnergy}>
          <View style={styles.readOnlyCopy}>
            <Text style={styles.fieldLabel}>Grid export from Solis</Text>
            <Text style={styles.hint}>
              Measured automatically since the latest baseline
            </Text>
          </View>
          <Text style={styles.readOnlyValue}>{Number(gridExport).toFixed(1)} kWh</Text>
        </View>
        <View style={styles.row}>
          <View style={[styles.cycleMetric, styles.compactField]}>
            <Text style={styles.fieldLabel}>Days elapsed</Text>
            <Text style={styles.cycleMetricValue}>{elapsedDays}</Text>
          </View>
          <View style={[styles.cycleMetric, styles.compactField]}>
            <Text style={styles.fieldLabel}>Billing-cycle days</Text>
            <Text style={styles.cycleMetricValue}>{cycleDays}</Text>
          </View>
        </View>
        <Text style={styles.hint}>
          Calculated automatically from the uploaded bill’s meter-reading dates.
        </Text>
        <View style={styles.row}>
          <View style={[styles.readOnlyEnergy, styles.compactField]}>
            <View style={styles.readOnlyCopy}>
              <Text style={styles.fieldLabel}>Uploaded export rate</Text>
              <Text style={styles.readOnlyValue}>₱{Number(exportRate).toFixed(2)}/kWh</Text>
            </View>
          </View>
          <View style={[styles.readOnlyEnergy, styles.compactField]}>
            <View style={styles.readOnlyCopy}>
              <Text style={styles.fieldLabel}>Uploaded carried credit</Text>
              <Text style={styles.readOnlyValue}>
                {peso.format(Number(appliedCredits) || 0)}
              </Text>
            </View>
          </View>
        </View>
        <View style={styles.switchRow}>
          <View style={styles.switchCopy}>
            <Text style={styles.fieldLabel}>Include ₱186.19 other charge</Text>
            <Text style={styles.hint}>Present on both uploaded bills</Text>
          </View>
          <Switch
            value={includeOtherCharges}
            onValueChange={setIncludeOtherCharges}
            trackColor={{ true: '#FDB813' }}
          />
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
              Meralco remains the authority for the official carried balance. Upload each new bill to reconcile it.
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
          Estimate only. Helios will not assume the residential sample rate. Your export-credit calculation activates when your own uploaded net-metering bill contains an export rate. Meralco rates and billing dates change monthly.
        </Text>
      </View>

      <Pressable style={styles.refreshButton} onPress={() => loadGridImport(true)}>
        <Text style={styles.refreshText}>Refresh from Solis now</Text>
      </Pressable>
      <Text style={styles.autoRefreshText}>
        Import and export refresh automatically every 15 minutes
      </Text>
    </ScrollView>
  );
}

function Field({ label, value, onChange, suffix, compact = false }: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  suffix?: string;
  compact?: boolean;
}) {
  return (
    <View style={[styles.field, compact && styles.compactField]}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <View style={styles.inputRow}>
        <TextInput
          style={styles.input}
          value={value}
          onChangeText={text => onChange(text.replace(/[^0-9.]/g, ''))}
          keyboardType="decimal-pad"
          selectTextOnFocus
        />
        {suffix && <Text style={styles.suffix}>{suffix}</Text>}
      </View>
    </View>
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
  uploadButton: { backgroundColor: '#162932', borderRadius: 16, padding: 16, borderWidth: 1, borderColor: '#2A4858' },
  uploadTitle: { color: '#F5F7F8', fontSize: 16, fontWeight: '700' },
  uploadHint: { color: '#86A1AF', fontSize: 12, marginTop: 4 },
  profileNotice: { color: '#8FDDBA', backgroundColor: '#10251D', padding: 12, borderRadius: 12, fontSize: 12 },
  qualityCard: { backgroundColor: '#0D1820', borderRadius: 16, padding: 16, borderWidth: 1, borderColor: '#27414F', gap: 7 },
  qualityHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  qualityTitle: { color: '#F5F7F8', fontSize: 16, fontWeight: '700' },
  qualityBadge: { overflow: 'hidden', borderRadius: 8, paddingHorizontal: 9, paddingVertical: 5, fontSize: 10, fontWeight: '800' },
  qualityFresh: { color: '#8FDDBA', backgroundColor: '#123126' },
  qualityDelayed: { color: '#FFD37A', backgroundColor: '#352A12' },
  qualityStale: { color: '#FF9A9A', backgroundColor: '#35191D' },
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
  sourceBadge: { alignSelf: 'flex-start', backgroundColor: '#162932', paddingHorizontal: 10, paddingVertical: 7, borderRadius: 9 },
  sourceBadgeText: { color: '#8FC5DD', fontSize: 10, fontWeight: '700' },
  meterBox: { gap: 10, backgroundColor: '#0A141A', padding: 13, borderRadius: 13 },
  confirmButton: { alignItems: 'center', backgroundColor: '#274B5D', padding: 11, borderRadius: 10 },
  confirmButtonText: { color: '#EAF5FA', fontWeight: '700' },
  readOnlyEnergy: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#0A141A', padding: 13, borderRadius: 12 },
  readOnlyCopy: { flex: 1, minWidth: 0 },
  readOnlyValue: { color: '#8FDDBA', fontSize: 18, fontWeight: '700', minWidth: 82, textAlign: 'right', flexShrink: 0 },
  creditBalance: { backgroundColor: '#10251D', borderRadius: 13, padding: 14 },
  creditBalanceLabel: { color: '#72CFA4', fontSize: 11, fontWeight: '800', letterSpacing: 1 },
  creditBalanceValue: { color: '#F5F7F8', fontSize: 28, fontWeight: '800', marginTop: 5 },
  cycleMetric: { backgroundColor: '#0A141A', padding: 13, borderRadius: 12, gap: 5 },
  cycleMetricValue: { color: '#F5F7F8', fontSize: 22, fontWeight: '700' },
  field: { gap: 7 },
  compactField: { flex: 1 },
  fieldLabel: { color: '#B6C1C7', fontSize: 13, fontWeight: '600' },
  inputRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#071117', borderRadius: 12, borderWidth: 1, borderColor: '#263943' },
  input: { flex: 1, color: '#F5F7F8', fontSize: 18, paddingHorizontal: 13, paddingVertical: 11 },
  suffix: { color: '#7F929D', paddingRight: 13 },
  switchRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  switchCopy: { flex: 1, gap: 3 },
  hint: { color: '#71838E', fontSize: 12 },
  body: { color: '#CCD4D8', lineHeight: 20 },
  referenceRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 10 },
  referencePeriod: { color: '#8597A1', flex: 1, fontSize: 12 },
  referenceValue: { color: '#DDE3E6', fontSize: 12, fontWeight: '600' },
  disclaimer: { color: '#71838E', fontSize: 12, lineHeight: 17, marginTop: 2 },
  refreshButton: { alignItems: 'center', padding: 14, borderRadius: 14, backgroundColor: '#FDB813' },
  refreshText: { color: '#142028', fontWeight: '800' },
  autoRefreshText: { color: '#657985', fontSize: 11, textAlign: 'center', marginTop: -8 },
});
