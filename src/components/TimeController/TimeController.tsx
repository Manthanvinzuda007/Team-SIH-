import { memo, useState, useCallback } from 'react';
import { Rewind, Play, Pause, FastForward } from 'lucide-react';
import styles from './TimeController.module.css';

export interface TimelineSlot {
  id: string;
  label: string;
  sublabel?: string;
  available: boolean;
}

export interface TimeControllerProps {
  slots?: TimelineSlot[];
  initialSlotId?: string;
}

export const MOCK_TIMELINE_SLOTS: TimelineSlot[] = [
  { id: 't1', label: '14 JUL 00:00Z', available: true },
  { id: 't2', label: '14 JUL 06:00Z', available: true },
  { id: 't3', label: '14 JUL 12:00Z', available: true },
  { id: 't4', label: '14 JUL 18:00Z', available: false },
  { id: 't5', label: '15 JUL 00:00Z', sublabel: '+6H', available: true },
  { id: 't6', label: '15 JUL 06:00Z', sublabel: '+12H', available: true },
  { id: 't7', label: '15 JUL 18:00Z', sublabel: '+24H', available: false },
];

const SPEEDS = [1, 2, 4];

function TimeControllerComponent({ slots = MOCK_TIMELINE_SLOTS, initialSlotId }: TimeControllerProps) {
  const [currentSlotId, setCurrentSlotId] = useState(initialSlotId ?? slots[1]?.id ?? slots[0]?.id);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speedIndex, setSpeedIndex] = useState(0);

  const currentIndex = slots.findIndex((s) => s.id === currentSlotId);

  const handleSlotClick = useCallback((slotId: string) => {
    setCurrentSlotId(slotId);
  }, []);

  const handlePlayToggle = useCallback(() => {
    setIsPlaying((p) => !p);
  }, []);

  const handleStepBack = useCallback(() => {
    setCurrentSlotId((prev) => {
      const idx = slots.findIndex((s) => s.id === prev);
      return slots[Math.max(0, idx - 1)]?.id ?? prev;
    });
  }, [slots]);

  const handleStepForward = useCallback(() => {
    setCurrentSlotId((prev) => {
      const idx = slots.findIndex((s) => s.id === prev);
      return slots[Math.min(slots.length - 1, idx + 1)]?.id ?? prev;
    });
  }, [slots]);

  const handleSpeedClick = useCallback(() => {
    setSpeedIndex((i) => (i + 1) % SPEEDS.length);
  }, []);

  const handleNowClick = useCallback(() => {
    setCurrentSlotId(slots[slots.length - 1]?.id);
  }, [slots]);

  return (
    <div className={styles.timeController}>
      <div className={styles.transportControls}>
        <button type="button" className={styles.iconBtn} onClick={handleStepBack} aria-label="Step back">
          <Rewind size={14} />
        </button>
        <button
          type="button"
          className={styles.iconBtnPrimary}
          onClick={handlePlayToggle}
          aria-label={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? <Pause size={14} /> : <Play size={14} />}
        </button>
        <button type="button" className={styles.iconBtn} onClick={handleStepForward} aria-label="Step forward">
          <FastForward size={14} />
        </button>
        <button type="button" className={styles.speedBtn} onClick={handleSpeedClick}>
          {SPEEDS[speedIndex]}x
        </button>
      </div>

      <div className={styles.timeline}>
        {slots.map((slot, idx) => (
          <button
            type="button"
            key={slot.id}
            className={`${styles.slot} ${idx === currentIndex ? styles.slotActive : ''}`}
            onClick={() => handleSlotClick(slot.id)}
          >
            <span className={styles.slotLabel}>{slot.label}</span>
            {slot.sublabel && <span className={styles.slotSublabel}>{slot.sublabel}</span>}
            <span
              className={`${styles.slotStatus} ${
                slot.available ? styles.slotAvailable : styles.slotUnavailable
              }`}
            >
              {slot.available ? 'AVAILABLE' : 'NO DATA'}
            </span>
          </button>
        ))}
      </div>

      <button type="button" className={styles.nowBtn} onClick={handleNowClick}>
        NOW
      </button>
    </div>
  );
}

export const TimeController = memo(TimeControllerComponent);