import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import DateTimePicker from '@react-native-community/datetimepicker';

import {
  assertHeliosConfigured,
  HELIOS_API_BASE,
  HELIOS_API_HEADERS,
} from '@/constants/helios';

type ChargingMode =
  | 'solar'
  | 'trip'
  | 'charge_now';

type HeliosStatus = {
  snapshot: {
    timestamp: string;
    solar_power_kw: number;
    house_load_kw: number;
    battery_soc_percent: number;
    battery_power_kw: number;
    grid_import_kw: number;
    grid_export_kw: number;
  };

  summary: {
    pv_surplus_before_battery_kw: number;
    grid_status: string;
    battery_status: string;
    tesla_available_power_kw: number;
    tesla_charging_allowed: boolean;
    tesla_charging_current_a: number;
    tesla_charging_reason: string;
  };

  tesla: {
    vehicle_id: string;
    battery_level_percent: number;
    charging_state: string;
    charging_power_kw: number;
    charging_current_a: number;
    battery_range_km: number;
    connected: boolean;
  };

  tesla_controller: {
    mode: string;
    action: string;
    target_current_a: number;
    reason: string;
    charging: boolean;
    current_a: number;
  };
};

type ChargingModeStatus = {
  mode: ChargingMode;
  simulated_tesla_soc_percent: number;
  target_soc_percent: number | null;
  departure_time: string | null;
  battery_capacity_kwh: number;
  max_ac_charging_power_kw: number;
  simulation: boolean;
};

const API_BASE = HELIOS_API_BASE;

export default function HomeScreen() {
  const [status, setStatus] =
    useState<HeliosStatus | null>(null);

  const [chargingMode, setChargingMode] =
    useState<ChargingModeStatus | null>(null);

  const [loading, setLoading] = useState(true);

  const [refreshing, setRefreshing] =
    useState(false);

  const [modeUpdating, setModeUpdating] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const [targetSoc, setTargetSoc] =
    useState('80');

  const [departureDate, setDepartureDate] =
    useState<Date | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      assertHeliosConfigured();

      const [
        statusResponse,
        modeResponse,
      ] = await Promise.all([
        fetch(`${API_BASE}/status`, {
          headers: HELIOS_API_HEADERS,
        }),
        fetch(`${API_BASE}/charging-mode`, {
          headers: HELIOS_API_HEADERS,
        }),
      ]);

      if (!statusResponse.ok) {
        throw new Error(
          `Status API returned ${statusResponse.status}`,
        );
      }

      if (!modeResponse.ok) {
        throw new Error(
          `Charging mode API returned ${modeResponse.status}`,
        );
      }

      const statusData: HeliosStatus =
        await statusResponse.json();

      const modeData: ChargingModeStatus =
        await modeResponse.json();

      setStatus(statusData);
      setChargingMode(modeData);

      if (
        modeData.target_soc_percent !== null
      ) {
        setTargetSoc(
          modeData.target_soc_percent.toString(),
        );
      }

      if (modeData.departure_time) {
        setDepartureDate(
          new Date(modeData.departure_time),
        );
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to reach Helios backend',
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();

    const interval = setInterval(
      loadData,
      15000,
    );

    return () =>
      clearInterval(interval);
  }, [loadData]);

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
  };

  const updateChargingMode =
    async (
      mode: ChargingMode,
    ) => {
      try {
        setModeUpdating(true);
        setError(null);

        const simulatedSoc =
          chargingMode
            ?.simulated_tesla_soc_percent ??
          status?.tesla
            .battery_level_percent ??
          35;

        const parsedTarget =
          Number(targetSoc);

        if (
          !Number.isFinite(parsedTarget) ||
          parsedTarget < 0 ||
          parsedTarget > 100
        ) {
          throw new Error(
            'Target SOC must be between 0 and 100%',
          );
        }

        let departureTime:
          | string
          | null = null;

        if (mode === 'trip') {
          if (!departureDate) {
            throw new Error(
              'Trip Mode requires a departure date and time.',
            );
          }

          if (
            departureDate.getTime()
            <= Date.now()
          ) {
            throw new Error(
              'Departure time must be in the future.',
            );
          }

          departureTime =
            departureDate.toISOString();
        }

        const response = await fetch(
          `${API_BASE}/charging-mode`,
          {
            method: 'PUT',
            headers: {
              'Content-Type':
                'application/json',
              ...HELIOS_API_HEADERS,
            },
            body: JSON.stringify({
              mode,
              simulated_tesla_soc_percent:
                simulatedSoc,
              target_soc_percent:
                parsedTarget,
              departure_time:
                departureTime,
            }),
          },
        );

        const responseData =
          await response.json();

        if (!response.ok) {
          throw new Error(
            responseData.detail ??
              `Charging mode update returned ${response.status}`,
          );
        }

        setChargingMode(
          responseData,
        );

        await loadData();
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'Unable to change charging mode',
        );
      } finally {
        setModeUpdating(false);
      }
    };

  if (loading) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator
          size="large"
          color="#FDB813"
        />

        <Text style={styles.loadingText}>
          Connecting to Helios...
        </Text>
      </View>
    );
  }

  const snapshot =
    status?.snapshot;

  const summary =
    status?.summary;

  const tesla =
    status?.tesla;

  const controller =
    status?.tesla_controller;

  const batteryCharging =
    summary?.battery_status ===
    'charging';

  const batteryDischarging =
    summary?.battery_status ===
    'discharging';

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={
        styles.content
      }
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          tintColor="#FDB813"
        />
      }
    >
      <View style={styles.header}>
        <View>
          <Text style={styles.logo}>
            HELIOS
          </Text>

          <Text style={styles.subtitle}>
            Home Energy
          </Text>
        </View>

        <View style={styles.live}>
          <View
            style={[
              styles.liveDot,
              error &&
                styles.offlineDot,
            ]}
          />

          <Text style={styles.liveText}>
            {error
              ? 'OFFLINE'
              : 'LIVE'}
          </Text>
        </View>
      </View>

      {error && (
        <View
          style={styles.errorCard}
        >
          <Text
            style={styles.errorTitle}
          >
            Helios notice
          </Text>

          <Text
            style={styles.errorText}
          >
            {error}
          </Text>
        </View>
      )}

      {snapshot &&
        summary &&
        controller && (
          <>
            <View
              style={styles.solarCard}
            >
              <Text
                style={
                  styles.cardEyebrow
                }
              >
                ☀️ SOLAR PRODUCTION
              </Text>

              <View
                style={
                  styles.solarValueRow
                }
              >
                <Text
                  style={
                    styles.solarValue
                  }
                >
                  {snapshot.solar_power_kw.toFixed(
                    2,
                  )}
                </Text>

                <Text
                  style={
                    styles.solarUnit
                  }
                >
                  kW
                </Text>
              </View>

              <Text
                style={
                  styles.solarCaption
                }
              >
                Powering your home right
                now
              </Text>
            </View>

            <ChargingModePanel
              chargingMode={
                chargingMode
              }
              targetSoc={
                targetSoc
              }
              setTargetSoc={
                setTargetSoc
              }
              departureDate={
                departureDate
              }
              setDepartureDate={
                setDepartureDate
              }
              modeUpdating={
                modeUpdating
              }
              onModeChange={
                updateChargingMode
              }
            />

            <ControllerPanel
              controller={controller}
              mode={
                chargingMode?.mode ??
                'solar'
              }
              teslaSoc={
                tesla?.battery_level_percent ??
                0
              }
              targetSoc={
                chargingMode
                  ?.target_soc_percent ??
                80
              }
            />

            <DynamicEnergyFlow
              solarPowerKw={
                snapshot.solar_power_kw
              }
              homeLoadKw={
                snapshot.house_load_kw
              }
              batteryPowerKw={
                snapshot.battery_power_kw
              }
              batterySocPercent={
                snapshot.battery_soc_percent
              }
              gridImportKw={
                snapshot.grid_import_kw
              }
              gridExportKw={
                snapshot.grid_export_kw
              }
              batteryStatus={
                summary.battery_status
              }
              teslaAvailablePowerKw={
                summary.tesla_available_power_kw
              }
              teslaConnected={
                tesla?.connected ??
                false
              }
            />

            <View
              style={styles.metrics}
            >
              <MetricCard
                title="HOME LOAD"
                value={
                  snapshot.house_load_kw.toFixed(
                    2,
                  )
                }
                unit="kW"
              />

              <MetricCard
                title="PV SURPLUS"
                value={
                  summary.pv_surplus_before_battery_kw.toFixed(
                    2,
                  )
                }
                unit="kW"
              />
            </View>

            <Text
              style={styles.metricHint}
            >
              PV surplus is calculated
              before battery charging.
            </Text>

            <View
              style={
                styles.batteryCard
              }
            >
              <View
                style={
                  styles.cardHeader
                }
              >
                <View>
                  <Text
                    style={
                      styles.cardEyebrow
                    }
                  >
                    HOME BATTERY
                  </Text>

                  <Text
                    style={
                      styles.batteryPercent
                    }
                  >
                    {snapshot.battery_soc_percent.toFixed(
                      0,
                    )}
                    %
                  </Text>
                </View>

                <View
                  style={
                    styles.batteryStatus
                  }
                >
                  <Text
                    style={
                      styles.batteryStatusText
                    }
                  >
                    {batteryCharging
                      ? '↑ CHARGING'
                      : batteryDischarging
                        ? '↓ DISCHARGING'
                        : '• IDLE'}
                  </Text>
                </View>
              </View>

              <View
                style={
                  styles.progressTrack
                }
              >
                <View
                  style={[
                    styles.progressFill,
                    {
                      width: `${Math.min(
                        snapshot.battery_soc_percent,
                        100,
                      )}%`,
                    },
                  ]}
                />
              </View>

              <View
                style={
                  styles.batteryFooter
                }
              >
                <Text
                  style={
                    styles.secondary
                  }
                >
                  Battery power
                </Text>

                <Text
                  style={
                    styles.secondaryStrong
                  }
                >
                  {Math.abs(
                    snapshot.battery_power_kw,
                  ).toFixed(2)}{' '}
                  kW
                </Text>
              </View>
            </View>

            <View
              style={styles.teslaCard}
            >
              <Text
                style={
                  styles.cardEyebrow
                }
              >
                TESLA SIMULATION
              </Text>

              <Text
                style={
                  styles.teslaTitle
                }
              >
                {tesla
                  ? `${tesla.battery_level_percent.toFixed(
                      0,
                    )}% simulated SOC`
                  : 'Vehicle unavailable'}
              </Text>

              <View
                style={
                  styles.teslaMetrics
                }
              >
                <View>
                  <Text
                    style={
                      styles.smallLabel
                    }
                  >
                    SOLAR AVAILABLE
                  </Text>

                  <Text
                    style={
                      styles.smallValue
                    }
                  >
                    {summary.tesla_available_power_kw.toFixed(
                      2,
                    )}{' '}
                    kW
                  </Text>
                </View>

                <View>
                  <Text
                    style={
                      styles.smallLabel
                    }
                  >
                    ENERGY ENGINE
                  </Text>

                  <Text
                    style={
                      styles.smallValue
                    }
                  >
                    {summary.tesla_charging_allowed
                      ? 'READY'
                      : 'WAIT'}
                  </Text>
                </View>
              </View>

              <Text
                style={styles.reason}
              >
                {
                  summary.tesla_charging_reason
                }
              </Text>
            </View>

            <View
              style={styles.gridRow}
            >
              <View>
                <Text
                  style={
                    styles.gridLabel
                  }
                >
                  Grid
                </Text>

                <Text
                  style={
                    styles.gridDetail
                  }
                >
                  Import{' '}
                  {snapshot.grid_import_kw.toFixed(
                    2,
                  )}{' '}
                  kW • Export{' '}
                  {snapshot.grid_export_kw.toFixed(
                    2,
                  )}{' '}
                  kW
                </Text>
              </View>

              <Text
                style={
                  styles.gridValue
                }
              >
                {summary.grid_status.toUpperCase()}
              </Text>
            </View>

            <Text
              style={styles.updated}
            >
              Last updated{' '}
              {new Date(
                snapshot.timestamp,
              ).toLocaleTimeString(
                [],
                {
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                },
              )}
            </Text>
          </>
        )}
    </ScrollView>
  );
}

function ChargingModePanel({
  chargingMode,
  targetSoc,
  setTargetSoc,
  departureDate,
  setDepartureDate,
  modeUpdating,
  onModeChange,
}: {
  chargingMode:
    | ChargingModeStatus
    | null;

  targetSoc: string;

  setTargetSoc:
    (value: string) => void;

  departureDate: Date | null;

  setDepartureDate:
    (value: Date) => void;

  modeUpdating: boolean;

  onModeChange:
    (mode: ChargingMode) => void;
}) {
  const mode =
    chargingMode?.mode ??
    'solar';

  const [showDatePicker, setShowDatePicker] =
    useState(false);

  const [showTimePicker, setShowTimePicker] =
    useState(false);

  const pickerDate =
    departureDate ??
    createDefaultDepartureDate();

  const updateDatePart = (
    selectedDate: Date,
  ) => {
    const updated =
      new Date(pickerDate);

    updated.setFullYear(
      selectedDate.getFullYear(),
      selectedDate.getMonth(),
      selectedDate.getDate(),
    );

    setDepartureDate(updated);
  };

  const updateTimePart = (
    selectedDate: Date,
  ) => {
    const updated =
      new Date(pickerDate);

    updated.setHours(
      selectedDate.getHours(),
      selectedDate.getMinutes(),
      0,
      0,
    );

    setDepartureDate(updated);
  };

  return (
    <View style={styles.modeCard}>
      <View style={styles.modeHeader}>
        <View>
          <Text
            style={styles.cardEyebrow}
          >
            TESLA CHARGING MODE
          </Text>

          <Text
            style={styles.modeTitle}
          >
            Simulation
          </Text>
        </View>

        <View
          style={
            styles.simulationBadge
          }
        >
          <Text
            style={
              styles.simulationBadgeText
            }
          >
            SAFE MODE
          </Text>
        </View>
      </View>

      <View
        style={styles.modeButtons}
      >
        <ModeButton
          title="☀️ Solar"
          active={
            mode === 'solar'
          }
          disabled={modeUpdating}
          onPress={() =>
            onModeChange('solar')
          }
        />

        <ModeButton
          title="🧳 Trip"
          active={
            mode === 'trip'
          }
          disabled={modeUpdating}
          onPress={() =>
            onModeChange('trip')
          }
        />

        <ModeButton
          title="⚡ Now"
          active={
            mode ===
            'charge_now'
          }
          disabled={modeUpdating}
          onPress={() =>
            onModeChange(
              'charge_now',
            )
          }
        />
      </View>

      <View style={styles.modeInfo}>
        <Text
          style={
            styles.modeDescription
          }
        >
          {mode === 'solar'
            ? 'Uses genuine solar surplus only. Grid fallback is disabled.'
            : mode === 'trip'
              ? 'Uses solar first, then allows grid charging when needed to meet your departure target.'
              : 'Allows immediate charging and grid fallback.'}
        </Text>
      </View>

      <View
        style={styles.tripInputs}
      >
        <View
          style={
            styles.inputColumn
          }
        >
          <Text
            style={
              styles.smallLabel
            }
          >
            TARGET SOC
          </Text>

          <TextInput
            style={styles.input}
            value={targetSoc}
            onChangeText={
              setTargetSoc
            }
            keyboardType="numeric"
            placeholder="80"
            placeholderTextColor="#53636D"
          />
        </View>
      </View>

      <Text
        style={styles.smallLabel}
      >
        TRIP DEPARTURE
      </Text>

      <View style={styles.departureRow}>
        <Pressable
          style={({ pressed }) => [
            styles.departureButton,
            pressed &&
              styles.modeButtonPressed,
          ]}
          onPress={() =>
            setShowDatePicker(true)
          }
        >
          <Text
            style={styles.departureIcon}
          >
            📅
          </Text>

          <View>
            <Text
              style={styles.departureLabel}
            >
              DATE
            </Text>

            <Text
              style={styles.departureValue}
            >
              {pickerDate.toLocaleDateString(
                undefined,
                {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                },
              )}
            </Text>
          </View>
        </Pressable>

        <Pressable
          style={({ pressed }) => [
            styles.departureButton,
            pressed &&
              styles.modeButtonPressed,
          ]}
          onPress={() =>
            setShowTimePicker(true)
          }
        >
          <Text
            style={styles.departureIcon}
          >
            🕐
          </Text>

          <View>
            <Text
              style={styles.departureLabel}
            >
              TIME
            </Text>

            <Text
              style={styles.departureValue}
            >
              {pickerDate.toLocaleTimeString(
                [],
                {
                  hour: 'numeric',
                  minute: '2-digit',
                },
              )}
            </Text>
          </View>
        </Pressable>
      </View>

      <Text
        style={styles.inputHint}
      >
        Required only for Trip Mode.
      </Text>

      {showDatePicker && (
        <DateTimePicker
          value={pickerDate}
          mode="date"
          display={
            Platform.OS === 'ios'
              ? 'inline'
              : 'default'
          }
          minimumDate={new Date()}
          onChange={(
            event,
            selectedDate,
          ) => {
            if (
              Platform.OS === 'android'
            ) {
              setShowDatePicker(false);
            }

            if (
              event.type === 'set' &&
              selectedDate
            ) {
              updateDatePart(
                selectedDate,
              );
            }
          }}
        />
      )}

      {showTimePicker && (
        <DateTimePicker
          value={pickerDate}
          mode="time"
          display={
            Platform.OS === 'ios'
              ? 'spinner'
              : 'default'
          }
          onChange={(
            event,
            selectedDate,
          ) => {
            if (
              Platform.OS === 'android'
            ) {
              setShowTimePicker(false);
            }

            if (
              event.type === 'set' &&
              selectedDate
            ) {
              updateTimePart(
                selectedDate,
              );
            }
          }}
        />
      )}

      {Platform.OS === 'ios' &&
        (showDatePicker ||
          showTimePicker) && (
          <Pressable
            style={
              styles.pickerDoneButton
            }
            onPress={() => {
              setShowDatePicker(false);
              setShowTimePicker(false);
            }}
          >
            <Text
              style={
                styles.pickerDoneText
              }
            >
              Done
            </Text>
          </Pressable>
        )}

      {modeUpdating && (
        <View
          style={
            styles.modeUpdating
          }
        >
          <ActivityIndicator
            size="small"
            color="#FDB813"
          />

          <Text
            style={
              styles.modeUpdatingText
            }
          >
            Updating charging mode...
          </Text>
        </View>
      )}
    </View>
  );
}

function ModeButton({
  title,
  active,
  disabled,
  onPress,
}: {
  title: string;
  active: boolean;
  disabled: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.modeButton,
        active &&
          styles.modeButtonActive,
        pressed &&
          styles.modeButtonPressed,
        disabled &&
          styles.modeButtonDisabled,
      ]}
    >
      <Text
        style={[
          styles.modeButtonText,
          active &&
            styles.modeButtonTextActive,
        ]}
      >
        {title}
      </Text>
    </Pressable>
  );
}

function ControllerPanel({
  controller,
  mode,
  teslaSoc,
  targetSoc,
}: {
  controller:
    HeliosStatus['tesla_controller'];

  mode: ChargingMode;

  teslaSoc: number;
  targetSoc: number;
}) {
  const action =
    controller.action.toUpperCase();

  const active =
    controller.charging ||
    controller.action ===
      'start' ||
    controller.action ===
      'set_current';

  return (
    <View
      style={
        styles.controllerCard
      }
    >
      <View
        style={
          styles.controllerHeader
        }
      >
        <View>
          <Text
            style={
              styles.cardEyebrow
            }
          >
            HELIOS DECISION
          </Text>

          <Text
            style={
              styles.controllerAction
            }
          >
            {action.replace(
              '_',
              ' ',
            )}
          </Text>
        </View>

        <View
          style={[
            styles.controllerState,
            active
              ? styles.controllerActive
              : styles.controllerWaiting,
          ]}
        >
          <Text
            style={
              styles.controllerStateText
            }
          >
            {active
              ? 'ACTIVE'
              : 'WAITING'}
          </Text>
        </View>
      </View>

      <View
        style={
          styles.controllerMetrics
        }
      >
        <ControllerMetric
          label="MODE"
          value={
            mode === 'charge_now'
              ? 'NOW'
              : mode.toUpperCase()
          }
        />

        <ControllerMetric
          label="TARGET"
          value={`${controller.target_current_a} A`}
        />

        <ControllerMetric
          label="TESLA"
          value={`${teslaSoc.toFixed(
            0,
          )}%`}
        />

        <ControllerMetric
          label="SOC GOAL"
          value={`${targetSoc.toFixed(
            0,
          )}%`}
        />
      </View>

      <Text
        style={
          styles.controllerReason
        }
      >
        {controller.reason}
      </Text>
    </View>
  );
}

function ControllerMetric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <View
      style={
        styles.controllerMetric
      }
    >
      <Text
        style={styles.smallLabel}
      >
        {label}
      </Text>

      <Text
        style={
          styles.controllerMetricValue
        }
      >
        {value}
      </Text>
    </View>
  );
}

function DynamicEnergyFlow({
  solarPowerKw,
  homeLoadKw,
  batteryPowerKw,
  batterySocPercent,
  gridImportKw,
  gridExportKw,
  batteryStatus,
  teslaAvailablePowerKw,
  teslaConnected,
}: {
  solarPowerKw: number;
  homeLoadKw: number;
  batteryPowerKw: number;
  batterySocPercent: number;
  gridImportKw: number;
  gridExportKw: number;
  batteryStatus: string;
  teslaAvailablePowerKw: number;
  teslaConnected: boolean;
}) {
  const solarActive =
    solarPowerKw > 0.05;

  const homeActive =
    homeLoadKw > 0.05;

  const batteryCharging =
    batteryStatus ===
    'charging';

  const batteryDischarging =
    batteryStatus ===
    'discharging';

  const importing =
    gridImportKw > 0.05;

  const exporting =
    gridExportKw > 0.05;

  const teslaFlowActive =
    teslaConnected &&
    teslaAvailablePowerKw >
      0.05;

  const solarToHomePower =
    Math.min(
      solarPowerKw,
      homeLoadKw,
    );

  return (
    <View
      style={styles.flowSection}
    >
      <View
        style={styles.flowHeader}
      >
        <Text
          style={styles.sectionTitle}
        >
          LIVE ENERGY FLOW
        </Text>

        <Text
          style={[
            styles.flowStatusText,
            !solarActive &&
              styles.flowStatusLow,
          ]}
        >
          {solarActive
            ? 'SOLAR ACTIVE'
            : 'LOW SOLAR'}
        </Text>
      </View>

      <FlowNode
        icon="☀️"
        label="Solar"
        value={`${solarPowerKw.toFixed(
          2,
        )} kW`}
        active={solarActive}
      />

      <FlowArrow
        direction="down"
        active={
          solarActive &&
          homeActive
        }
        label={
          solarActive &&
          homeActive
            ? `${solarToHomePower.toFixed(
                2,
              )} kW`
            : undefined
        }
      />

      <FlowNode
        icon="🏠"
        label="Home"
        value={`${homeLoadKw.toFixed(
          2,
        )} kW`}
        active={homeActive}
      />

      <View
        style={styles.branchRow}
      >
        <View
          style={
            styles.branchColumn
          }
        >
          <FlowArrow
            direction={
              batteryCharging
                ? 'down'
                : 'up'
            }
            active={
              batteryCharging ||
              batteryDischarging
            }
            label={
              Math.abs(
                batteryPowerKw,
              ) > 0.05
                ? `${Math.abs(
                    batteryPowerKw,
                  ).toFixed(
                    2,
                  )} kW`
                : undefined
            }
          />

          <FlowNode
            icon="🔋"
            label="Battery"
            value={`${batterySocPercent.toFixed(
              0,
            )}%`}
            detail={batteryStatus}
            active={
              batteryCharging ||
              batteryDischarging
            }
          />
        </View>

        <View
          style={
            styles.branchColumn
          }
        >
          <FlowArrow
            direction={
              importing
                ? 'up'
                : 'down'
            }
            active={
              importing ||
              exporting
            }
            label={
              importing
                ? `${gridImportKw.toFixed(
                    2,
                  )} kW`
                : exporting
                  ? `${gridExportKw.toFixed(
                      2,
                    )} kW`
                  : undefined
            }
          />

          <FlowNode
            icon="⚡"
            label="Grid"
            value={
              importing
                ? `${gridImportKw.toFixed(
                    2,
                  )} kW`
                : exporting
                  ? `${gridExportKw.toFixed(
                      2,
                    )} kW`
                  : '0.00 kW'
            }
            detail={
              importing
                ? 'importing'
                : exporting
                  ? 'exporting'
                  : 'balanced'
            }
            active={
              importing ||
              exporting
            }
          />
        </View>
      </View>

      <FlowArrow
        direction="down"
        active={
          teslaFlowActive
        }
        label={
          teslaFlowActive
            ? `${teslaAvailablePowerKw.toFixed(
                2,
              )} kW`
            : undefined
        }
      />

      <FlowNode
        icon="🚗"
        label="Tesla"
        value={
          teslaConnected
            ? `${teslaAvailablePowerKw.toFixed(
                2,
              )} kW`
            : 'Future'
        }
        detail={
          teslaConnected
            ? 'smart charging'
            : 'not connected'
        }
        active={
          teslaFlowActive
        }
      />
    </View>
  );
}

function FlowNode({
  icon,
  label,
  value,
  detail,
  active = false,
}: {
  icon: string;
  label: string;
  value: string;
  detail?: string;
  active?: boolean;
}) {
  return (
    <View
      style={[
        styles.flowNode,
        active &&
          styles.flowNodeActive,
      ]}
    >
      <Text
        style={styles.flowIcon}
      >
        {icon}
      </Text>

      <Text
        style={styles.flowLabel}
      >
        {label}
      </Text>

      <Text
        style={[
          styles.flowValue,
          active &&
            styles.flowValueActive,
        ]}
      >
        {value}
      </Text>

      {detail && (
        <Text
          style={[
            styles.flowDetail,
            active &&
              styles.flowDetailActive,
          ]}
        >
          {detail}
        </Text>
      )}
    </View>
  );
}

function FlowArrow({
  direction,
  active,
  label,
}: {
  direction: 'up' | 'down';
  active: boolean;
  label?: string;
}) {
  return (
    <View
      style={
        styles.flowArrowContainer
      }
    >
      {label && (
        <Text
          style={[
            styles.flowArrowLabel,
            active &&
              styles.flowArrowLabelActive,
          ]}
        >
          {label}
        </Text>
      )}

      <Text
        style={[
          styles.flowArrow,
          active
            ? styles.flowArrowActive
            : styles.flowArrowInactive,
        ]}
      >
        {direction === 'down'
          ? '↓'
          : '↑'}
      </Text>
    </View>
  );
}

function MetricCard({
  title,
  value,
  unit,
}: {
  title: string;
  value: string;
  unit: string;
}) {
  return (
    <View
      style={styles.metricCard}
    >
      <Text
        style={styles.smallLabel}
      >
        {title}
      </Text>

      <View
        style={
          styles.metricValueRow
        }
      >
        <Text
          style={
            styles.metricValue
          }
        >
          {value}
        </Text>

        <Text
          style={
            styles.metricUnit
          }
        >
          {unit}
        </Text>
      </View>
    </View>
  );
}

function createDefaultDepartureDate() {
  const date = new Date();

  date.setDate(
    date.getDate() + 1,
  );

  date.setHours(
    7,
    0,
    0,
    0,
  );

  return date;
}

const styles =
  StyleSheet.create({
    screen: {
      flex: 1,
      backgroundColor: '#071018',
    },

    content: {
      paddingHorizontal: 18,
      paddingTop: 64,
      paddingBottom: 50,
    },

    loading: {
      flex: 1,
      backgroundColor: '#071018',
      justifyContent: 'center',
      alignItems: 'center',
    },

    loadingText: {
      color: '#AAB6BE',
      marginTop: 14,
    },

    header: {
      flexDirection: 'row',
      justifyContent:
        'space-between',
      alignItems: 'center',
      marginBottom: 26,
    },

    logo: {
      color: '#FFFFFF',
      fontSize: 30,
      fontWeight: '900',
      letterSpacing: 2,
    },

    subtitle: {
      color: '#74838E',
      fontSize: 14,
      marginTop: 2,
    },

    live: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: '#112029',
      borderRadius: 30,
      paddingHorizontal: 12,
      paddingVertical: 8,
    },

    liveDot: {
      width: 7,
      height: 7,
      borderRadius: 4,
      backgroundColor: '#58D68D',
      marginRight: 7,
    },

    offlineDot: {
      backgroundColor: '#E67E7E',
    },

    liveText: {
      color: '#C8D1D7',
      fontSize: 11,
      fontWeight: '800',
      letterSpacing: 1,
    },

    errorCard: {
      backgroundColor: '#352329',
      borderRadius: 20,
      padding: 18,
      marginBottom: 16,
    },

    errorTitle: {
      color: '#FFFFFF',
      fontSize: 15,
      fontWeight: '800',
    },

    errorText: {
      color: '#D5B2B9',
      fontSize: 12,
      marginTop: 6,
    },

    solarCard: {
      backgroundColor: '#14252E',
      borderRadius: 28,
      padding: 24,
      marginBottom: 16,
    },

    cardEyebrow: {
      color: '#81919C',
      fontSize: 11,
      fontWeight: '800',
      letterSpacing: 1.3,
    },

    solarValueRow: {
      flexDirection: 'row',
      alignItems: 'flex-end',
      marginTop: 10,
    },

    solarValue: {
      color: '#FFFFFF',
      fontSize: 58,
      lineHeight: 65,
      fontWeight: '900',
    },

    solarUnit: {
      color: '#FDB813',
      fontSize: 19,
      fontWeight: '700',
      marginLeft: 8,
      marginBottom: 9,
    },

    solarCaption: {
      color: '#8E9DA6',
      fontSize: 14,
      marginTop: 3,
    },

    modeCard: {
      backgroundColor: '#0D1820',
      borderRadius: 26,
      padding: 20,
      marginBottom: 14,
    },

    modeHeader: {
      flexDirection: 'row',
      justifyContent:
        'space-between',
      alignItems: 'center',
    },

    modeTitle: {
      color: '#FFFFFF',
      fontSize: 21,
      fontWeight: '800',
      marginTop: 5,
    },

    simulationBadge: {
      backgroundColor: '#173629',
      borderRadius: 12,
      paddingHorizontal: 10,
      paddingVertical: 7,
    },

    simulationBadgeText: {
      color: '#58D68D',
      fontSize: 9,
      fontWeight: '900',
      letterSpacing: 1,
    },

    modeButtons: {
      flexDirection: 'row',
      gap: 8,
      marginTop: 20,
    },

    modeButton: {
      flex: 1,
      backgroundColor: '#15242C',
      borderRadius: 14,
      paddingVertical: 12,
      alignItems: 'center',
      borderWidth: 1,
      borderColor: '#1A2B34',
    },

    modeButtonActive: {
      borderColor: '#FDB813',
      backgroundColor: '#282919',
    },

    modeButtonPressed: {
      opacity: 0.75,
    },

    modeButtonDisabled: {
      opacity: 0.5,
    },

    modeButtonText: {
      color: '#7C8C96',
      fontSize: 11,
      fontWeight: '800',
    },

    modeButtonTextActive: {
      color: '#FDB813',
    },

    modeInfo: {
      backgroundColor: '#101E26',
      borderRadius: 14,
      padding: 12,
      marginTop: 12,
      marginBottom: 16,
    },

    modeDescription: {
      color: '#8998A1',
      fontSize: 12,
      lineHeight: 18,
    },

    tripInputs: {
      flexDirection: 'row',
      gap: 12,
      marginBottom: 14,
    },

    departureRow: {
      flexDirection: 'row',
      gap: 10,
      marginTop: 8,
    },

    departureButton: {
      flex: 1,
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: '#14232B',
      borderRadius: 14,
      borderWidth: 1,
      borderColor: '#1C303A',
      paddingHorizontal: 12,
      paddingVertical: 13,
    },

    departureIcon: {
      fontSize: 20,
      marginRight: 9,
    },

    departureLabel: {
      color: '#71818C',
      fontSize: 9,
      fontWeight: '800',
      letterSpacing: 1,
    },

    departureValue: {
      color: '#FFFFFF',
      fontSize: 13,
      fontWeight: '700',
      marginTop: 3,
    },

    pickerDoneButton: {
      alignSelf: 'flex-end',
      backgroundColor: '#FDB813',
      borderRadius: 12,
      paddingHorizontal: 18,
      paddingVertical: 10,
      marginTop: 10,
    },

    pickerDoneText: {
      color: '#071018',
      fontSize: 12,
      fontWeight: '900',
    },

    inputColumn: {
      flex: 1,
    },

    input: {
      backgroundColor: '#14232B',
      borderRadius: 13,
      color: '#FFFFFF',
      paddingHorizontal: 13,
      paddingVertical: 12,
      fontSize: 14,
      marginTop: 7,
      borderWidth: 1,
      borderColor: '#1C303A',
    },

    inputHint: {
      color: '#52636D',
      fontSize: 10,
      marginTop: 7,
    },

    modeUpdating: {
      flexDirection: 'row',
      alignItems: 'center',
      marginTop: 12,
    },

    modeUpdatingText: {
      color: '#8998A1',
      fontSize: 11,
      marginLeft: 8,
    },

    controllerCard: {
      backgroundColor: '#0D1820',
      borderRadius: 26,
      padding: 20,
      marginBottom: 14,
    },

    controllerHeader: {
      flexDirection: 'row',
      justifyContent:
        'space-between',
      alignItems: 'flex-start',
    },

    controllerAction: {
      color: '#FFFFFF',
      fontSize: 27,
      fontWeight: '900',
      marginTop: 5,
    },

    controllerState: {
      borderRadius: 12,
      paddingHorizontal: 10,
      paddingVertical: 7,
    },

    controllerActive: {
      backgroundColor: '#17472E',
    },

    controllerWaiting: {
      backgroundColor: '#332B1F',
    },

    controllerStateText: {
      color: '#FFFFFF',
      fontSize: 9,
      fontWeight: '900',
      letterSpacing: 1,
    },

    controllerMetrics: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      marginTop: 20,
      gap: 10,
    },

    controllerMetric: {
      width: '47%',
      backgroundColor: '#111F27',
      borderRadius: 14,
      padding: 12,
    },

    controllerMetricValue: {
      color: '#FFFFFF',
      fontSize: 17,
      fontWeight: '800',
      marginTop: 5,
    },

    controllerReason: {
      color: '#7D8D96',
      fontSize: 12,
      lineHeight: 18,
      marginTop: 15,
    },

    flowSection: {
      backgroundColor: '#0D1820',
      borderRadius: 26,
      padding: 20,
      marginBottom: 14,
    },

    flowHeader: {
      flexDirection: 'row',
      justifyContent:
        'space-between',
      alignItems: 'center',
      marginBottom: 18,
    },

    sectionTitle: {
      color: '#71818C',
      fontSize: 11,
      fontWeight: '800',
      letterSpacing: 1.3,
    },

    flowStatusText: {
      color: '#58D68D',
      fontSize: 9,
      fontWeight: '900',
      letterSpacing: 1,
    },

    flowStatusLow: {
      color: '#74838E',
    },

    flowNode: {
      alignItems: 'center',
      backgroundColor: '#121F27',
      borderRadius: 20,
      paddingVertical: 16,
      paddingHorizontal: 12,
      minHeight: 112,
    },

    flowNodeActive: {
      borderWidth: 1,
      borderColor: '#FDB813',
      backgroundColor: '#16252D',
    },

    flowIcon: {
      fontSize: 23,
    },

    flowLabel: {
      color: '#80909A',
      fontSize: 11,
      marginTop: 6,
    },

    flowValue: {
      color: '#B5C0C6',
      fontSize: 18,
      fontWeight: '800',
      marginTop: 4,
    },

    flowValueActive: {
      color: '#FFFFFF',
    },

    flowDetail: {
      color: '#687984',
      fontSize: 10,
      textTransform: 'capitalize',
      marginTop: 3,
    },

    flowDetailActive: {
      color: '#FDB813',
    },

    flowArrowContainer: {
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: 42,
    },

    flowArrow: {
      fontSize: 22,
      fontWeight: '800',
    },

    flowArrowActive: {
      color: '#FDB813',
    },

    flowArrowInactive: {
      color: '#2A3942',
    },

    flowArrowLabel: {
      color: '#53636D',
      fontSize: 10,
      fontWeight: '700',
      marginBottom: -2,
    },

    flowArrowLabelActive: {
      color: '#AAB7BE',
    },

    branchRow: {
      flexDirection: 'row',
      gap: 12,
    },

    branchColumn: {
      flex: 1,
    },

    metrics: {
      flexDirection: 'row',
      gap: 12,
      marginBottom: 8,
    },

    metricCard: {
      flex: 1,
      backgroundColor: '#0D1820',
      borderRadius: 22,
      padding: 18,
    },

    metricHint: {
      color: '#53636D',
      fontSize: 10,
      marginBottom: 14,
      marginHorizontal: 4,
    },

    smallLabel: {
      color: '#71818C',
      fontSize: 10,
      fontWeight: '800',
      letterSpacing: 1,
    },

    metricValueRow: {
      flexDirection: 'row',
      alignItems: 'flex-end',
      marginTop: 10,
    },

    metricValue: {
      color: '#FFFFFF',
      fontSize: 27,
      fontWeight: '800',
    },

    metricUnit: {
      color: '#7E8E98',
      fontSize: 12,
      marginLeft: 5,
      marginBottom: 4,
    },

    batteryCard: {
      backgroundColor: '#0D1820',
      borderRadius: 26,
      padding: 20,
      marginBottom: 14,
    },

    cardHeader: {
      flexDirection: 'row',
      justifyContent:
        'space-between',
      alignItems: 'flex-start',
    },

    batteryPercent: {
      color: '#FFFFFF',
      fontSize: 38,
      fontWeight: '900',
      marginTop: 5,
    },

    batteryStatus: {
      backgroundColor: '#17262D',
      borderRadius: 12,
      paddingHorizontal: 10,
      paddingVertical: 7,
    },

    batteryStatusText: {
      color: '#A9B7BE',
      fontSize: 10,
      fontWeight: '800',
    },

    progressTrack: {
      height: 9,
      backgroundColor: '#1A2931',
      borderRadius: 20,
      overflow: 'hidden',
      marginTop: 16,
    },

    progressFill: {
      height: '100%',
      backgroundColor: '#FDB813',
      borderRadius: 20,
    },

    batteryFooter: {
      flexDirection: 'row',
      justifyContent:
        'space-between',
      marginTop: 12,
    },

    secondary: {
      color: '#70808A',
      fontSize: 12,
    },

    secondaryStrong: {
      color: '#B4C0C6',
      fontSize: 12,
      fontWeight: '700',
    },

    teslaCard: {
      backgroundColor: '#0D1820',
      borderRadius: 26,
      padding: 20,
      marginBottom: 14,
    },

    teslaTitle: {
      color: '#FFFFFF',
      fontSize: 20,
      fontWeight: '800',
      marginTop: 6,
    },

    teslaMetrics: {
      flexDirection: 'row',
      justifyContent:
        'space-between',
      marginTop: 22,
      marginBottom: 18,
    },

    smallValue: {
      color: '#FFFFFF',
      fontSize: 19,
      fontWeight: '800',
      marginTop: 5,
    },

    reason: {
      color: '#75858F',
      fontSize: 12,
      lineHeight: 18,
    },

    gridRow: {
      flexDirection: 'row',
      justifyContent:
        'space-between',
      alignItems: 'center',
      backgroundColor: '#0D1820',
      borderRadius: 18,
      padding: 16,
    },

    gridLabel: {
      color: '#B6C2C8',
      fontSize: 13,
      fontWeight: '700',
    },

    gridDetail: {
      color: '#657680',
      fontSize: 10,
      marginTop: 4,
    },

    gridValue: {
      color: '#B6C2C8',
      fontSize: 12,
      fontWeight: '800',
      letterSpacing: 0.8,
    },

    updated: {
      color: '#55656F',
      textAlign: 'center',
      fontSize: 11,
      marginTop: 18,
    },
  });
