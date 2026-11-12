<script setup lang="ts">

withDefaults(defineProps<{ variant?: 'primary'|'secondary'|'plain'|'destructive'; size?: 'sm'|'md'; disabled?: boolean; busy?: boolean; type?: 'button'|'submit'|'reset' }>(), { variant:'secondary',size:'md',type:'button',disabled:false,busy:false })

</script>
<template><button :type="type" class="ui-button" :class="[`ui-button--${variant}`,`ui-button--${size}`]" :disabled="disabled || busy" :aria-busy="busy || undefined"><slot name="icon"/><slot/></button></template>
