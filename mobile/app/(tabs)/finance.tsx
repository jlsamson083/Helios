import { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Dimensions, ScrollView, StyleSheet, Text, View } from 'react-native';
import { BarChart } from 'react-native-chart-kit';

import { HELIOS_API_BASE, HELIOS_API_HEADERS } from '@/constants/helios';

type MonthSummary = {
  month: string;
  income_php: number;
  expenses_php: number;
  remaining_php: number;
};

type FinanceEntry = {
  id: number;
  transaction_date: string;
  direction: 'income' | 'expense';
  description: string;
  category: string;
  amount_php: number;
  source: string;
};

const peso = new Intl.NumberFormat('en-PH', {
  style: 'currency',
  currency: 'PHP',
  maximumFractionDigits: 0,
});

function monthLabel(value: string) {
  return new Date(`${value}-01T00:00:00`).toLocaleDateString('en-PH', {
    month: 'short',
    year: '2-digit',
  });
}

export default function FinanceScreen() {
  const [months, setMonths] = useState<MonthSummary[]>([]);
  const [entries, setEntries] = useState<FinanceEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const base = HELIOS_API_BASE.replace('/energy', '');
      const options = {
        headers: HELIOS_API_HEADERS,
        credentials: 'include' as const,
        cache: 'no-store' as const,
      };
      const [summaryResponse, entriesResponse] = await Promise.all([
        fetch(`${base}/finance/summary`, options),
        fetch(`${base}/finance/entries`, options),
      ]);
      if (summaryResponse.status === 403 || entriesResponse.status === 403) {
        throw new Error('Finance is available only to the Eros account.');
      }
      if (!summaryResponse.ok || !entriesResponse.ok) {
        throw new Error('Unable to load private finance data.');
      }
      setMonths((await summaryResponse.json()).months);
      setEntries((await entriesResponse.json()).entries);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load finance data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const totals = useMemo(() => months.reduce(
    (result, month) => ({
      income: result.income + month.income_php,
      expenses: result.expenses + month.expenses_php,
      remaining: result.remaining + month.remaining_php,
    }),
    { income: 0, expenses: 0, remaining: 0 },
  ), [months]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#FDB813" size="large" />
        <Text style={styles.muted}>Loading private finance data…</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.lock}>🔒</Text>
        <Text style={styles.errorTitle}>Private finance</Text>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  const recentMonths = months.slice(-6);
  const chartWidth = Math.max(Dimensions.get('window').width - 40, 340);

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Finance</Text>
      <Text style={styles.subtitle}>Private monthly salary and expense tracking</Text>

      <View style={styles.summaryRow}>
        <SummaryCard label="Income" value={peso.format(totals.income)} color="#8FDDBA" />
        <SummaryCard label="Expenses" value={peso.format(totals.expenses)} color="#FF9A9A" />
      </View>
      <View style={styles.balanceCard}>
        <Text style={styles.balanceLabel}>REMAINING BALANCE</Text>
        <Text style={styles.balanceValue}>{peso.format(totals.remaining)}</Text>
      </View>

      {recentMonths.length > 0 ? (
        <View style={styles.chartCard}>
          <Text style={styles.cardTitle}>Income vs expenses (₱ thousands)</Text>
          <View style={styles.legend}>
            <Text style={styles.incomeLegend}>● Income</Text>
            <Text style={styles.expenseLegend}>● Expenses</Text>
          </View>
          <BarChart
            data={{
              labels: recentMonths.map(month => monthLabel(month.month)),
              datasets: [
                { data: recentMonths.map(month => month.income_php / 1000), color: () => '#8FDDBA' },
                { data: recentMonths.map(month => month.expenses_php / 1000), color: () => '#FF8A80' },
              ],
            }}
            width={chartWidth - 34}
            height={260}
            fromZero
            yAxisLabel="₱"
            yAxisSuffix="k"
            chartConfig={{
              backgroundColor: '#0D1820',
              backgroundGradientFrom: '#0D1820',
              backgroundGradientTo: '#0D1820',
              color: opacity => `rgba(245,247,248,${opacity})`,
              labelColor: opacity => `rgba(184,196,202,${opacity})`,
              decimalPlaces: 0,
              barPercentage: 0.55,
              propsForBackgroundLines: { stroke: '#20303A' },
            }}
            style={styles.chart}
          />
        </View>
      ) : (
        <View style={styles.emptyCard}>
          <Text style={styles.cardTitle}>Ready for bank statements</Text>
          <Text style={styles.emptyText}>
            Forward one sample bank email with its PDF attachment to the Helios Gmail account. After its format is verified, Helios can import salary and expense transactions automatically.
          </Text>
          <Text style={styles.privateNote}>Only the Eros account can access this page or its API.</Text>
        </View>
      )}

      {entries.length > 0 && (
        <View style={styles.entriesCard}>
          <Text style={styles.cardTitle}>Recent transactions</Text>
          {entries.slice(0, 20).map(entry => (
            <View key={entry.id} style={styles.entry}>
              <View style={styles.entryCopy}>
                <Text style={styles.entryTitle}>{entry.description}</Text>
                <Text style={styles.entryMeta}>{entry.transaction_date} · {entry.category}</Text>
              </View>
              <Text style={entry.direction === 'income' ? styles.income : styles.expense}>
                {entry.direction === 'income' ? '+' : '−'}{peso.format(entry.amount_php)}
              </Text>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

function SummaryCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <View style={styles.summaryCard}>
      <Text style={styles.summaryLabel}>{label}</Text>
      <Text style={[styles.summaryValue, { color }]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#071117' },
  content: { padding: 20, paddingTop: 30, paddingBottom: 44, gap: 16 },
  center: { flex: 1, backgroundColor: '#071117', alignItems: 'center', justifyContent: 'center', padding: 28, gap: 10 },
  muted: { color: '#8FA1AC' },
  lock: { fontSize: 38 },
  errorTitle: { color: '#F5F7F8', fontSize: 24, fontWeight: '800' },
  error: { color: '#FF9A9A', textAlign: 'center' },
  title: { color: '#F5F7F8', fontSize: 32, fontWeight: '900' },
  subtitle: { color: '#8FA1AC', marginTop: -10 },
  summaryRow: { flexDirection: 'row', gap: 12 },
  summaryCard: { flex: 1, minWidth: 0, backgroundColor: '#0D1820', borderRadius: 16, borderWidth: 1, borderColor: '#20303A', padding: 15 },
  summaryLabel: { color: '#82949E', fontSize: 12 },
  summaryValue: { fontSize: 19, fontWeight: '800', marginTop: 5 },
  balanceCard: { backgroundColor: '#10251D', borderRadius: 18, padding: 18, borderWidth: 1, borderColor: '#244A39' },
  balanceLabel: { color: '#72CFA4', fontSize: 11, fontWeight: '900', letterSpacing: 1 },
  balanceValue: { color: '#F5F7F8', fontSize: 30, fontWeight: '900', marginTop: 6 },
  chartCard: { backgroundColor: '#0D1820', borderRadius: 18, padding: 17, borderWidth: 1, borderColor: '#20303A', overflow: 'hidden' },
  chart: { marginTop: 12, marginLeft: -10, borderRadius: 12 },
  legend: { flexDirection: 'row', gap: 16, marginTop: 10 },
  incomeLegend: { color: '#8FDDBA', fontSize: 12, fontWeight: '700' },
  expenseLegend: { color: '#FF9A9A', fontSize: 12, fontWeight: '700' },
  cardTitle: { color: '#F5F7F8', fontSize: 18, fontWeight: '800' },
  emptyCard: { backgroundColor: '#0D1820', borderRadius: 18, padding: 18, borderWidth: 1, borderColor: '#20303A', gap: 9 },
  emptyText: { color: '#B8C4CA', lineHeight: 21 },
  privateNote: { color: '#8FDDBA', fontSize: 12 },
  entriesCard: { backgroundColor: '#0D1820', borderRadius: 18, padding: 18, borderWidth: 1, borderColor: '#20303A', gap: 4 },
  entry: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#192A34' },
  entryCopy: { flex: 1 },
  entryTitle: { color: '#E5EAED', fontWeight: '700' },
  entryMeta: { color: '#748791', fontSize: 11, marginTop: 3 },
  income: { color: '#8FDDBA', fontWeight: '800' },
  expense: { color: '#FF9A9A', fontWeight: '800' },
});
