import { onBeforeUnmount, onMounted, ref } from 'vue'
import { Timeline } from './Timeline'

export function useMathTimeline(renderFrame: (progress: number) => void, reducedMotion = false) {
  const progress = ref(1)
  const playing = ref(false)
  const speed = ref(1)
  const direction = ref<1 | -1>(1)
  const loop = ref(true)
  let timeline: Timeline | null = null

  onMounted(() => {
    timeline = new Timeline(renderFrame, (snapshot) => { progress.value = snapshot.progress; playing.value = snapshot.playing; speed.value = snapshot.speed; direction.value = snapshot.direction; loop.value = snapshot.loop }, reducedMotion)
    timeline.seek(1)
  })
  onBeforeUnmount(() => timeline?.dispose())

  return {
    progress, playing, speed, direction, loop,
    play: () => timeline?.play(),
    pause: () => timeline?.pause(),
    reset: () => timeline?.reset(),
    seek: (value: number) => timeline?.seek(value),
    setSpeed: (value: number) => timeline?.setSpeed(value),
    reverse: () => timeline?.reverse(),
    setLoop: (value: boolean) => timeline?.setLoop(value),
  }
}
