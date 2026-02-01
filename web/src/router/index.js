import Vue from 'vue'
import Router from 'vue-router'

import ErrorPage from '../components/ErrorPage.vue'
import HomePage from '../views/LandingPage.vue'

Vue.use(Router)

const routes = [
    {
        name: "home",
        path: "/",
        component: HomePage,
    },
    {
        name: "error",
        path: "*",
        component: ErrorPage,
    },
];

const router = new Router({
    mode: "history",
    routes,
    scrollBehavior() { return { x: 0, y: 0 } }
});

// Navigation guard for protected routes
// import { auth } from '@/firebase';

// router.beforeEach((to, from, next) => {
//     const requiresAuth = to.matched.some(record => record.meta.requiresAuth);
//     const currentUser = auth.currentUser;

//     if (requiresAuth && !currentUser) {
//         next('/');
//     } else {
//         next();
//     }
// });

export default router;