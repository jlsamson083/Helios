import { useCallback, useEffect, useState } from 'react';
import {
    ActivityIndicator,
    Dimensions,
    Pressable,
    RefreshControl,
    ScrollView,
    StyleSheet,
    Text,
    View,
} from 'react-native';
import { LineChart } from 'react-native-chart-kit';

import {
  assertHeliosConfigured,
  HELIOS_API_BASE,
  HELIOS_API_HEADERS,
} from '@/constants/helios';

const SUMMARY_URL =
  `${HELIOS_API_BASE}/history/summary`;

const TIMESERIES_URL =
  `${HELIOS_API_BASE}/history/timeseries?limit=500`;

type Period = 'today' | 'month' | 'year';

type EnergyPeriod = {
  solar_generation_kwh: number;
  home_load_kwh: number;
  battery_charge_kwh: number;
  battery_discharge_kwh: number;
  grid_import_kwh: number;
  grid_export_kwh: number;
};

type HistoryResponse = {
  today: EnergyPeriod;
  month: EnergyPeriod;
  year: EnergyPeriod;
};

type Snapshot = {
  timestamp: string;
  solar_power_kw: number;
  house_load_kw: number;
  battery_soc_percent: number;
  battery_power_kw: number;
  grid_import_kw: number;
  grid_export_kw: number;
};

type TimeseriesResponse = {
  items: Snapshot[];
};

export default function HistoryScreen() {
  const [history, setHistory] =
    useState<HistoryResponse | null>(null);

  const [snapshots, setSnapshots] =
    useState<Snapshot[]>([]);

  const [period, setPeriod] =
    useState<Period>('today');

  const [loading, setLoading] =
    useState(true);

  const [refreshing, setRefreshing] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    try {
      setError(null);
      assertHeliosConfigured();

      const [summaryResponse, timeseriesResponse] =
        await Promise.all([
          fetch(SUMMARY_URL, {
            headers: HELIOS_API_HEADERS,
          }),
          fetch(TIMESERIES_URL, {
            headers: HELIOS_API_HEADERS,
          }),
        ]);

      if (!summaryResponse.ok) {
        throw new Error(
          `Summary API returned ${summaryResponse.status}`,
        );
      }

      if (!timeseriesResponse.ok) {
        throw new Error(
          `Timeseries API returned ${timeseriesResponse.status}`,
        );
      }

      const summaryData: HistoryResponse =
        await summaryResponse.json();

      const timeseriesData: TimeseriesResponse =
        await timeseriesResponse.json();

      setHistory(summaryData);
      setSnapshots(timeseriesData.items);
    } catch (err) {
      console.error(err);

      setError(
        err instanceof Error
          ? err.message
          : 'Unable to connect to Helios',
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const onRefresh = async () => {
    setRefreshing(true);
    await loadHistory();
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator
          size="large"
          color="#FDB813"
        />

        <Text style={styles.loadingText}>
          Loading energy history...
        </Text>
      </View>
    );
  }

  const selected = history?.[period];

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          tintColor="#FDB813"
        />
      }
    >
      <Text style={styles.title}>History</Text>

      <Text style={styles.subtitle}>
        Your home energy performance
      </Text>

      <View style={styles.periodSelector}>
        <PeriodButton
          title="Today"
          active={period === 'today'}
          onPress={() => setPeriod('today')}
        />

        <PeriodButton
          title="Month"
          active={period === 'month'}
          onPress={() => setPeriod('month')}
        />

        <PeriodButton
          title="Year"
          active={period === 'year'}
          onPress={() => setPeriod('year')}
        />
      </View>

      {error && (
        <View style={styles.errorCard}>
          <Text style={styles.errorTitle}>
            Helios offline
          </Text>

          <Text style={styles.errorText}>
            {error}
          </Text>
        </View>
      )}

      {selected && (
        <>
          <View style={styles.heroCard}>
            <Text style={styles.eyebrow}>
              SOLAR GENERATED
            </Text>

            <View style={styles.valueRow}>
              <Text style={styles.heroValue}>
                {selected.solar_generation_kwh.toFixed(1)}
              </Text>

              <Text style={styles.heroUnit}>
                kWh
              </Text>
            </View>

            <Text style={styles.heroCaption}>
              Clean energy produced by your solar system
            </Text>
          </View>

          {period === 'today' && (
            <PowerChart snapshots={snapshots} />
          )}

          <EnergyComparisonChart
            solar={selected.solar_generation_kwh}
            home={selected.home_load_kwh}
            period={period}
          />

          <View style={styles.grid}>
            <EnergyCard
              label="Home"
              value={selected.home_load_kwh}
              description="Consumed"
            />

            <EnergyCard
              label="Grid"
              value={selected.grid_import_kwh}
              description="Imported"
            />

            <EnergyCard
              label="Battery"
              value={selected.battery_charge_kwh}
              description="Charged"
            />

            <EnergyCard
              label="Battery"
              value={selected.battery_discharge_kwh}
              description="Discharged"
            />
          </View>

          <View style={styles.exportCard}>
            <View>
              <Text style={styles.exportLabel}>
                GRID EXPORT
              </Text>

              <Text style={styles.exportDescription}>
                Energy sent back to the grid
              </Text>
            </View>

            <View style={styles.exportValueRow}>
              <Text style={styles.exportValue}>
                {selected.grid_export_kwh.toFixed(2)}
              </Text>

              <Text style={styles.exportUnit}>
                kWh
              </Text>
            </View>
          </View>
        </>
      )}

      <Text style={styles.footer}>
        Pull down to refresh from Solis
      </Text>
    </ScrollView>
  );
}


function PowerChart({
  snapshots,
}: {
  snapshots: Snapshot[];
}) {
  if (snapshots.length < 2) {
    return (
      <View style={styles.chartCard}>
        <Text style={styles.chartEyebrow}>
          TODAY POWER CURVE
        </Text>

        <Text style={styles.chartTitle}>
          Collecting data...
        </Text>

        <Text style={styles.chartHint}>
          Helios needs at least two stored snapshots
          before drawing the chart.
        </Text>
      </View>
    );
  }

  /*
   * Keep the chart readable on a phone.
   * We still retain every point in SQLite; this only
   * reduces how many labels/points we draw at once.
   */
  const maxChartPoints = 24;

  const step = Math.max(
    Math.ceil(snapshots.length / maxChartPoints),
    1,
  );

  const chartPoints = snapshots.filter(
    (_, index) =>
      index % step === 0 ||
      index === snapshots.length - 1,
  );

  const labels = chartPoints.map(
    (item, index) => {
      /*
       * Showing every X-axis label becomes unreadable,
       * so display a few evenly distributed labels.
       */
      const labelEvery = Math.max(
        Math.ceil(chartPoints.length / 5),
        1,
      );

      if (
        index % labelEvery !== 0 &&
        index !== chartPoints.length - 1
      ) {
        return '';
      }

      return new Date(
        item.timestamp,
      ).toLocaleTimeString([], {
        hour: 'numeric',
        minute: '2-digit',
      });
    },
  );

  const solar = chartPoints.map(
    item => item.solar_power_kw,
  );

  const home = chartPoints.map(
    item => item.house_load_kw,
  );

  const screenWidth =
    Dimensions.get('window').width;

  return (
    <View style={styles.chartCard}>
      <View style={styles.chartHeader}>
        <View>
          <Text style={styles.chartEyebrow}>
            TODAY POWER CURVE
          </Text>

          <Text style={styles.chartTitle}>
            Solar vs Home
          </Text>
        </View>

        <Text style={styles.liveLabel}>
          LIVE
        </Text>
      </View>

      <View style={styles.legendRow}>
        <View style={styles.legendItem}>
          <View style={styles.solarDot} />
          <Text style={styles.legendText}>
            Solar
          </Text>
        </View>

        <View style={styles.legendItem}>
          <View style={styles.homeDot} />
          <Text style={styles.legendText}>
            Home
          </Text>
        </View>
      </View>

      <LineChart
        data={{
          labels,
          datasets: [
            {
              data: solar,
              color: () => '#FDB813',
              strokeWidth: 3,
            },
            {
              data: home,
              color: () => '#5F85A6',
              strokeWidth: 3,
            },
          ],
          legend: [],
        }}
        width={screenWidth - 64}
        height={220}
        fromZero
        withDots={chartPoints.length <= 12}
        withInnerLines={false}
        withOuterLines={false}
        withVerticalLines={false}
        yAxisSuffix=" kW"
        chartConfig={{
          backgroundColor: '#0D1820',
          backgroundGradientFrom: '#0D1820',
          backgroundGradientTo: '#0D1820',
          decimalPlaces: 1,
          color: () => '#74838E',
          labelColor: () => '#74838E',
          propsForBackgroundLines: {
            stroke: '#17252D',
          },
          propsForLabels: {
            fontSize: 9,
          },
        }}
        bezier
        style={styles.lineChart}
      />

      <Text style={styles.chartHint}>
        Built from snapshots stored by Helios.
      </Text>
    </View>
  );
}


function EnergyComparisonChart({
  solar,
  home,
  period,
}: {
  solar: number;
  home: number;
  period: Period;
}) {
  const maxValue = Math.max(
    solar,
    home,
    1,
  );

  const solarWidth = `${Math.min(
    (solar / maxValue) * 100,
    100,
  )}%` as `${number}%`;

  const homeWidth = `${Math.min(
    (home / maxValue) * 100,
    100,
  )}%` as `${number}%`;


  const periodLabel =
    period === 'today'
      ? 'Today'
      : period === 'month'
        ? 'This month'
        : 'This year';

  return (
    <View style={styles.chartCard}>
      <View style={styles.chartHeader}>
        <View>
          <Text style={styles.chartEyebrow}>
            ENERGY COMPARISON
          </Text>

          <Text style={styles.chartTitle}>
            Solar vs Home
          </Text>
        </View>

        <Text style={styles.chartPeriod}>
          {periodLabel}
        </Text>
      </View>

      <View style={styles.comparisonRow}>
        <View style={styles.chartLabelRow}>
          <Text style={styles.chartLabel}>
            Solar
          </Text>

          <Text style={styles.chartNumber}>
            {solar.toFixed(1)} kWh
          </Text>
        </View>

        <View style={styles.barTrack}>
          <View
            style={[
              styles.bar,
              styles.solarBar,
              {
                width: solarWidth,
              },
            ]}
          />
        </View>
      </View>

      <View style={styles.comparisonRow}>
        <View style={styles.chartLabelRow}>
          <Text style={styles.chartLabel}>
            Home
          </Text>

          <Text style={styles.chartNumber}>
            {home.toFixed(1)} kWh
          </Text>
        </View>

        <View style={styles.barTrack}>
          <View
            style={[
              styles.bar,
              styles.homeBar,
              {
                width: homeWidth,
              },
            ]}
          />
        </View>
      </View>


    </View>
  );
}


function PeriodButton({
  title,
  active,
  onPress,
}: {
  title: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[
        styles.periodButton,
        active && styles.periodButtonActive,
      ]}
    >
      <Text
        style={[
          styles.periodText,
          active && styles.periodTextActive,
        ]}
      >
        {title}
      </Text>
    </Pressable>
  );
}


function EnergyCard({
  label,
  value,
  description,
}: {
  label: string;
  value: number;
  description: string;
}) {
  return (
    <View style={styles.energyCard}>
      <Text style={styles.cardLabel}>
        {label.toUpperCase()}
      </Text>

      <View style={styles.cardValueRow}>
        <Text style={styles.cardValue}>
          {value.toFixed(1)}
        </Text>

        <Text style={styles.cardUnit}>
          kWh
        </Text>
      </View>

      <Text style={styles.cardDescription}>
        {description}
      </Text>
    </View>
  );
}


const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: '#071018',
  },

  center: {
    flex: 1,
    backgroundColor: '#071018',
    alignItems: 'center',
    justifyContent: 'center',
  },

  loadingText: {
    color: '#84939D',
    marginTop: 14,
  },

  content: {
    paddingHorizontal: 20,
    paddingTop: 64,
    paddingBottom: 120,
  },

  title: {
    color: '#FFFFFF',
    fontSize: 32,
    fontWeight: '900',
  },

  subtitle: {
    color: '#74838E',
    fontSize: 14,
    marginTop: 4,
    marginBottom: 24,
  },

  periodSelector: {
    flexDirection: 'row',
    backgroundColor: '#0D1820',
    padding: 5,
    borderRadius: 16,
    marginBottom: 18,
  },

  periodButton: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 11,
    borderRadius: 12,
  },

  periodButtonActive: {
    backgroundColor: '#FDB813',
  },

  periodText: {
    color: '#74838E',
    fontWeight: '700',
  },

  periodTextActive: {
    color: '#071018',
  },

  heroCard: {
    backgroundColor: '#14252E',
    borderRadius: 26,
    padding: 22,
    marginBottom: 12,
  },

  eyebrow: {
    color: '#FDB813',
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.2,
  },

  valueRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginTop: 10,
  },

  heroValue: {
    color: '#FFFFFF',
    fontSize: 48,
    fontWeight: '900',
  },

  heroUnit: {
    color: '#84939D',
    fontSize: 18,
    fontWeight: '700',
    marginLeft: 8,
  },

  heroCaption: {
    color: '#84939D',
    fontSize: 13,
    marginTop: 4,
  },

  chartCard: {
    backgroundColor: '#0D1820',
    borderRadius: 24,
    padding: 20,
    marginBottom: 12,
    overflow: 'hidden',
  },

  chartHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
  },

  chartEyebrow: {
    color: '#74838E',
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1,
  },

  chartTitle: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: '900',
    marginTop: 5,
  },

  chartPeriod: {
    color: '#FDB813',
    fontSize: 11,
    fontWeight: '800',
  },

  liveLabel: {
    color: '#58D68D',
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 1,
  },

  legendRow: {
    flexDirection: 'row',
    marginBottom: 6,
    gap: 18,
  },

  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
  },

  solarDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#FDB813',
    marginRight: 6,
  },

  homeDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#5F85A6',
    marginRight: 6,
  },

  legendText: {
    color: '#84939D',
    fontSize: 11,
  },

  lineChart: {
    marginLeft: -15,
    borderRadius: 16,
  },

  chartHint: {
    color: '#53636D',
    fontSize: 10,
    lineHeight: 15,
    marginTop: 4,
  },

  comparisonRow: {
    marginBottom: 20,
  },

  chartLabelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },

  chartLabel: {
    color: '#A7B4BC',
    fontSize: 13,
    fontWeight: '700',
  },

  chartNumber: {
    color: '#84939D',
    fontSize: 12,
    fontWeight: '700',
  },

  barTrack: {
    height: 12,
    borderRadius: 20,
    backgroundColor: '#17252D',
    overflow: 'hidden',
  },

  bar: {
    height: '100%',
    borderRadius: 20,
  },

  solarBar: {
    backgroundColor: '#FDB813',
  },

  homeBar: {
    backgroundColor: '#5F85A6',
  },

  chartSummary: {
    borderTopWidth: 1,
    borderTopColor: '#18262E',
    paddingTop: 16,
    flexDirection: 'row',
    justifyContent: 'space-between',
  },

  chartSummaryLabel: {
    color: '#74838E',
    fontSize: 12,
  },

  chartSummaryValue: {
    fontSize: 14,
    fontWeight: '900',
  },

  positive: {
    color: '#58D68D',
  },

  negative: {
    color: '#E67E7E',
  },

  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },

  energyCard: {
    width: '48.5%',
    backgroundColor: '#0D1820',
    borderRadius: 20,
    padding: 17,
    marginBottom: 12,
  },

  cardLabel: {
    color: '#74838E',
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1,
  },

  cardValueRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginTop: 10,
  },

  cardValue: {
    color: '#FFFFFF',
    fontSize: 25,
    fontWeight: '900',
  },

  cardUnit: {
    color: '#74838E',
    fontSize: 11,
    marginLeft: 4,
  },

  cardDescription: {
    color: '#84939D',
    fontSize: 12,
    marginTop: 5,
  },

  exportCard: {
    backgroundColor: '#0D1820',
    borderRadius: 20,
    padding: 18,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },

  exportLabel: {
    color: '#74838E',
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1,
  },

  exportDescription: {
    color: '#84939D',
    fontSize: 12,
    marginTop: 5,
  },

  exportValueRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
  },

  exportValue: {
    color: '#FFFFFF',
    fontSize: 23,
    fontWeight: '900',
  },

  exportUnit: {
    color: '#74838E',
    fontSize: 11,
    marginLeft: 4,
  },

  errorCard: {
    backgroundColor: '#2A1717',
    borderRadius: 18,
    padding: 18,
    marginBottom: 14,
  },

  errorTitle: {
    color: '#FFFFFF',
    fontWeight: '800',
    fontSize: 15,
  },

  errorText: {
    color: '#B9A0A0',
    fontSize: 12,
    marginTop: 5,
  },

  footer: {
    color: '#53636D',
    fontSize: 11,
    textAlign: 'center',
    marginTop: 20,
  },
});
