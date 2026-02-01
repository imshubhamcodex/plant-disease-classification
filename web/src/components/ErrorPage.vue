<template>
  <v-container fluid class="d-flex align-center justify-center text-center mt-12 pt-12">
    <div>
      <v-img id="error-image" src="../assets/error.png" max-width="450" class="mb-4 mx-auto" />
      <h1 class="h1 mb-2">404 Page not Found</h1>
      <h3 class="h2 mb-2">Looks like you're lost.</h3>

      <router-link to="/">
        <v-btn class="mt-5" style="font-weight: bold;" color="primary">
          <v-icon left>mdi-home</v-icon>
          Go to Home
        </v-btn>
      </router-link>
    </div>
  </v-container>
</template>

<style scoped>
h3 {
  font-style: italic;
}

/* Mobile responsiveness */
@media screen and (max-width: 600px) {
  h1 {
    font-size: 20px;
  }

  h3 {
    font-size: 15px;
  }

  #error-image {
    width: 300px !important;
  }
}
</style>